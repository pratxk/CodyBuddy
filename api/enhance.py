"""
VibeEngineer endpoint — POST /api/enhance.

Takes current files + a natural-language instruction and returns the complete
updated file set via a single LLM call (same single-pass parse pattern as
the coder node).
"""
import logging
import uuid
from datetime import datetime as _dt, timezone as _tz

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.llm import CODER_CHAIN, CODER_CHAIN_PREMIUM, chat, strip_code_fences
from agent.premium_scaffold import is_premium_shaped, preserve_premium_scaffold
from agent.prompts import CODER_SYSTEM_PROMPT, vibe_prompt, vibe_prompt_premium
from agent.scaffold import (detect_framework, normalize_files,
                           parse_reply_and_files)
from auth.dependencies import get_current_user
from db.database import SessionLocal
from db.models import Project, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enhance", tags=["enhance"])


class EnhanceRequest(BaseModel):
    project_id: str | None = None
    files: dict[str, str]
    instruction: str
    session_id: str | None = None  # ponytail: kept for backward compat, ignored for ownership
    premium: bool = False  # honored ONLY for SUPER_ADMIN (server-side gate below)


class EnhanceResponse(BaseModel):
    project_id: str
    files: dict[str, str]
    reply: str  # ponytail: short first-person message from the VibeEngineer (two-way chat)


@router.post("", response_model=EnhanceResponse)
def enhance(
    req: EnhanceRequest,
    current_user: User = Depends(get_current_user),
) -> EnhanceResponse:
    if not req.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction must not be empty")
    if not req.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    # ponytail: never trust the client flag — premium is honored only for SUPER_ADMIN
    # (mirrors api.generate._resolve_premium); a non-admin asking for premium gets standard.
    premium = bool(req.premium) and getattr(current_user, "role", "") == "SUPER_ADMIN"
    chain = CODER_CHAIN_PREMIUM if premium else CODER_CHAIN

    if is_premium_shaped(req.files):
        # SCOPED edit: send only the editable surface (not the frozen /ui + /lib kit)
        # + the primitive cheatsheet, and ask for ONLY the changed files. This keeps
        # a premium edit fast + reliable instead of re-writing all ~22 files.
        editable = {p: c for p, c in req.files.items()
                    if not p.startswith(("/ui/", "/lib/"))}
        raw = chat(
            vibe_prompt_premium(editable, req.instruction),
            chain=chain, system=CODER_SYSTEM_PROMPT, max_tokens=16000, agent="enhance",
        )
        reply, changed = parse_reply_and_files(raw, strip_code_fences)
        reply = reply or "Applied your changes."
        # Merge the partial changes over the current app, then re-freeze the kit + deps.
        merged = normalize_files({**req.files, **changed}, "react")
        updated_files = preserve_premium_scaffold(req.files, merged)
    else:
        raw = chat(
            vibe_prompt(req.files, req.instruction, premium=premium),
            chain=chain, system=CODER_SYSTEM_PROMPT, max_tokens=20000 if premium else 8192, agent="enhance",
        )
        reply, parsed = parse_reply_and_files(raw, strip_code_fences)
        reply = reply or "Applied your changes."
        # ponytail: infer framework so static/next apps aren't React-normalized.
        updated_files = normalize_files(parsed, detect_framework(req.files))

    project_id = _upsert_project(req.project_id, current_user.id, req.instruction, updated_files, source="enhance")
    return EnhanceResponse(project_id=project_id, files=updated_files, reply=reply)


_MAX_VERSIONS = 15


def snapshot_version(row: Project, source: str, label: str) -> None:
    """Append the row's CURRENT files as a recoverable version BEFORE it's
    overwritten, capped at the most recent _MAX_VERSIONS. So every agent change
    (enhance/UX/OnCall) or revert preserves the prior state for one-click revert."""
    if not getattr(row, "files", None):
        return
    entry = {
        "id": str(uuid.uuid4()),
        "at": _dt.now(_tz.utc).isoformat(),
        "source": source,
        "label": (label or "").strip()[:80],
        "files": row.files,
    }
    prior = list(row.versions or [])
    prior.append(entry)
    row.versions = prior[-_MAX_VERSIONS:]


def _upsert_project(project_id: str | None, user_id: uuid.UUID, instruction: str,
                    files: dict, source: str = "edit") -> str:
    """Update existing project (owned by user) or create a new one; returns the project UUID string.

    Snapshots the PRIOR files as a version before overwriting an existing row, so
    a bad change can be reverted."""
    try:
        with SessionLocal() as db:
            if project_id:
                row = db.get(Project, uuid.UUID(project_id))
                if row and row.user_id == user_id:
                    snapshot_version(row, source, instruction)
                    row.files = files
                    db.commit()
                    db.refresh(row)
                    return str(row.id)
                # ponytail: if not found / user mismatch, fall through to create
            row = Project(
                session_id="",
                user_id=user_id,
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
