"""
UX MASTER endpoint — POST /api/uxmaster.

A multimodal design-critique agent: the user uploads a SCREENSHOT of their running app;
UX MASTER critiques the ACTUAL rendered UI and returns the complete improved file set via a
single vision LLM call (Gemini 2.5 Flash). Mirrors /api/enhance (premium gate, parse → reply,
normalize → upsert) but adds a `needs_verification` flag the agent uses to ask for a fresh
screenshot.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.llm import VISION_CHAIN, chat_vision
from agent.premium_scaffold import is_premium_shaped, preserve_premium_scaffold
from agent.prompts import CODER_SYSTEM_PROMPT, uxmaster_prompt
from agent.scaffold import (detect_framework, normalize_files,
                           parse_uxmaster_response)
from agent.llm import strip_code_fences
from api.enhance import _upsert_project  # ponytail: reuse the same owned-project upsert
from auth.dependencies import get_current_user
from db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/uxmaster", tags=["uxmaster"])


class UXMasterRequest(BaseModel):
    project_id: str | None = None
    files: dict[str, str]
    image: str  # base64 data URL of the running-app screenshot
    instruction: str | None = None
    session_id: str | None = None  # ponytail: kept for backward compat, ignored for ownership
    premium: bool = False  # honored ONLY for SUPER_ADMIN (server-side gate below)


class UXMasterResponse(BaseModel):
    project_id: str
    files: dict[str, str]
    reply: str  # first-person message from UX MASTER (what it saw + changed)
    needs_verification: bool  # True → UX MASTER wants a fresh screenshot to verify


@router.post("", response_model=UXMasterResponse)
def uxmaster(
    req: UXMasterRequest,
    current_user: User = Depends(get_current_user),
) -> UXMasterResponse:
    # ponytail: validate at the boundary — the screenshot is the whole point of this agent.
    if not req.image or not req.image.strip().startswith("data:"):
        raise HTTPException(status_code=400, detail="image must be a base64 data URL")
    if not req.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    instruction = (req.instruction or "").strip()
    # ponytail: never trust the client flag — premium is honored only for SUPER_ADMIN (mirrors enhance).
    premium = bool(req.premium) and getattr(current_user, "role", "") == "SUPER_ADMIN"
    raw = chat_vision(
        uxmaster_prompt(req.files, instruction, image_provided=True),
        req.image,
        chain=VISION_CHAIN,  # gemini-only — the multimodal model in the pool
        system=CODER_SYSTEM_PROMPT,
        max_tokens=20000 if premium else 8192, agent="uxmaster",
    )
    # ponytail: ONE call emits the conversational reply, the verify boolean, and the files.
    reply, needs_verification, parsed = parse_uxmaster_response(raw, strip_code_fences)
    reply = reply or "Reviewed your screenshot and refined the UI."
    updated_files = normalize_files(parsed, detect_framework(req.files))
    # ponytail: same premium-safety as enhance — never drop/clobber the baked /ui kit.
    if is_premium_shaped(req.files):
        updated_files = preserve_premium_scaffold(req.files, updated_files)

    label = instruction or "screenshot review"
    project_id = _upsert_project(req.project_id, current_user.id, f"UX Master: {label}", updated_files, source="uxmaster")
    return UXMasterResponse(
        project_id=project_id,
        files=updated_files,
        reply=reply,
        needs_verification=needs_verification,
    )
