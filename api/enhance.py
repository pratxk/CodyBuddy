"""
VibeEngineer endpoint — POST /api/enhance.

Takes current files + a natural-language instruction and returns the complete
updated file set via a single LLM call (same single-pass parse pattern as
the coder node).
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.llm import CODER_CHAIN, CODER_CHAIN_PREMIUM, chat, strip_code_fences
from agent.prompts import CODER_SYSTEM_PROMPT, vibe_prompt
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
    raw = chat(
        vibe_prompt(req.files, req.instruction, premium=premium),
        chain=chain,
        system=CODER_SYSTEM_PROMPT,
        max_tokens=20000 if premium else 8192,
    )
    # ponytail: ONE call emits both the conversational reply and the files.
    reply, parsed = parse_reply_and_files(raw, strip_code_fences)
    reply = reply or "Applied your changes."
    # ponytail: infer framework from the incoming files so static/next apps aren't React-normalized.
    # The vibe prompt itself stays React-worded for this pass (acceptable per spec).
    updated_files = normalize_files(parsed, detect_framework(req.files))

    project_id = _upsert_project(req.project_id, current_user.id, req.instruction, updated_files)
    return EnhanceResponse(project_id=project_id, files=updated_files, reply=reply)


def _upsert_project(project_id: str | None, user_id: uuid.UUID, instruction: str, files: dict) -> str:
    """Update existing project (owned by user) or create a new one; returns the project UUID string."""
    try:
        with SessionLocal() as db:
            if project_id:
                row = db.get(Project, uuid.UUID(project_id))
                if row and row.user_id == user_id:
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
