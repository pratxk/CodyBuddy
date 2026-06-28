"""
VibeEngineer endpoint — POST /api/enhance.

Takes current files + a natural-language instruction and returns the complete
updated file set via a single LLM call (same single-pass parse pattern as
the coder node).
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.llm import CODER_CHAIN, chat, strip_code_fences
from agent.prompts import CODER_SYSTEM_PROMPT, vibe_prompt
from agent.scaffold import normalize_files, parse_multi_file_response
from db.database import SessionLocal
from db.models import Project

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enhance", tags=["enhance"])


class EnhanceRequest(BaseModel):
    project_id: str | None = None
    files: dict[str, str]
    instruction: str
    session_id: str


class EnhanceResponse(BaseModel):
    project_id: str
    files: dict[str, str]


@router.post("", response_model=EnhanceResponse)
def enhance(req: EnhanceRequest) -> EnhanceResponse:
    if not req.session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction must not be empty")
    if not req.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    # Single LLM call — reuse coder chain + single-pass parser
    raw = chat(
        vibe_prompt(req.files, req.instruction),
        chain=CODER_CHAIN,
        system=CODER_SYSTEM_PROMPT,
        max_tokens=8192,
    )
    parsed = parse_multi_file_response(raw, strip_code_fences)
    updated_files = normalize_files(parsed)

    project_id = _upsert_project(req.project_id, req.session_id, req.instruction, updated_files)
    return EnhanceResponse(project_id=project_id, files=updated_files)


def _upsert_project(project_id: str | None, session_id: str, instruction: str, files: dict) -> str:
    """Update existing project or create a new one; returns the project UUID string."""
    try:
        with SessionLocal() as db:
            if project_id:
                row = db.get(Project, uuid.UUID(project_id))
                if row and str(row.session_id) == session_id:
                    row.files = files
                    db.commit()
                    db.refresh(row)
                    return str(row.id)
                # ponytail: if not found / session mismatch, fall through to create
            row = Project(
                session_id=session_id,
                title=f"Enhanced: {instruction[:60]}",
                brief=instruction,
                files=files,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return str(row.id)
    except Exception as exc:  # noqa: BLE001
        logger.error("DB upsert failed: %s", exc)
        # ponytail: return a stable placeholder so the FE still gets files
        return project_id or str(uuid.uuid4())
