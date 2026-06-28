import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.events import AgentEventEmitter, BUILD_TOPOLOGY
from agent.graph import run_build
from auth.dependencies import get_current_user
from db.database import SessionLocal
from db.models import Project, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

_executor = ThreadPoolExecutor(max_workers=4)
_job_queues: Dict[str, asyncio.Queue] = {}  # NOTE: single-consumer per job; redesign planned in a later task.
_DONE = "__DONE__"
_ERR = "__ERR__:"


def shutdown_executor() -> None:
    """Shut down the thread pool gracefully (call from app lifespan on shutdown)."""
    _executor.shutdown(wait=False)


class GenerateRequest(BaseModel):
    brief: str
    session_id: str | None = None  # ponytail: kept for backward compat, ignored for ownership


def _persist_project(user_id: str | None, title: str, brief: str, files: dict) -> str | None:
    """Save a Project row; returns the new UUID string or None on failure."""
    if not user_id:
        return None
    try:
        with SessionLocal() as db:
            row = Project(session_id="", user_id=uuid.UUID(user_id), title=title, brief=brief, files=files)
            db.add(row)
            db.commit()
            db.refresh(row)
            return str(row.id)
    except Exception as exc:  # noqa: BLE001  ponytail: DB hiccup must not break the build
        logger.error("DB persist failed (non-fatal): %s", exc)
        return None


def _run_job(job_id, queue, loop, brief, user_id=None):
    emitter = AgentEventEmitter(loop, queue, BUILD_TOPOLOGY)
    try:
        out = run_build(brief, emitter=emitter)
        project_id = _persist_project(user_id, out["plan"].name, brief, out["files"])
        payload: dict = {"type": "result", "name": out["plan"].name, "files": out["files"]}
        if project_id:
            payload["project_id"] = project_id
        asyncio.run_coroutine_threadsafe(queue.put(json.dumps(payload)), loop)
        asyncio.run_coroutine_threadsafe(queue.put(_DONE), loop)
    except Exception as exc:  # noqa: BLE001
        logger.error("Generate job %s failed: %s", job_id, exc)
        asyncio.run_coroutine_threadsafe(queue.put(f"{_ERR}{exc}"), loop)


@router.post("/start")
async def generate_start(
    req: GenerateRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    if not req.brief.strip():
        raise HTTPException(status_code=400, detail="brief is required")
    job_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _job_queues[job_id] = queue
    user_id = str(current_user.id)
    _executor.submit(_run_job, job_id, queue, loop, req.brief, user_id)
    return {"job_id": job_id}


async def _sse(job_id, queue) -> AsyncGenerator[str, None]:
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
            if msg == _DONE:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            if isinstance(msg, str) and msg.startswith(_ERR):
                yield f"data: {json.dumps({'type': 'error', 'message': msg[len(_ERR):]})}\n\n"
                break
            yield f"data: {msg}\n\n"
    finally:
        _job_queues.pop(job_id, None)


# ponytail: events stream is open (no auth) — job_id UUID is already a nonce
@router.get("/events/{job_id}")
async def generate_events(job_id: str) -> StreamingResponse:
    queue = _job_queues.get(job_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Job not found or already completed")
    return StreamingResponse(
        _sse(job_id, queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
