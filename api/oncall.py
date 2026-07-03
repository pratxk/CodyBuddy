"""
OnCallAgent endpoint — POST /api/oncall.

Takes the current Sandpack files + a runtime/compile error string and returns
the complete corrected file set via a single LLM call.

ponytail: same shape as /api/enhance — reuses vibe machinery, _upsert_project,
parse + normalize. Only difference: instruction is auto-derived from the error.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.llm import CODER_CHAIN, chat, strip_code_fences
from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES
from agent.prompts import CODER_SYSTEM_PROMPT, oncall_prompt
from agent.scaffold import (detect_framework, normalize_files,
                           parse_multi_file_response)
from api.enhance import _upsert_project
from auth.dependencies import get_current_user
from db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oncall", tags=["oncall"])

# ponytail: a premium app is recognised by the baked barrel it always ships with.
_PREMIUM_MARKER = "/ui/index.js"


def _is_premium_shaped(files: dict[str, str]) -> bool:
    """True when the app carries the baked premium kit (its barrel is present)."""
    return _PREMIUM_MARKER in files


def _preserve_premium_scaffold(
    original: dict[str, str], fixed: dict[str, str]
) -> dict[str, str]:
    """Make an OnCall fix safe for premium apps.

    OnCall regenerates the WHOLE file set via a non-premium LLM call, which will
    NOT reproduce the 12 baked ``/ui/*`` primitives, ``/lib/format.js`` or
    ``/data/mock.js`` — dropping them would destroy the app (the barrel would
    import files that no longer exist → "Could not find module './ui'").

    Fix: layer the LLM's changes over the ORIGINAL files (so nothing the LLM
    silently omitted is lost), then re-overlay the baked kit LAST so the frozen
    primitives + styles + format lib can never be clobbered by an LLM re-emission.
    """
    # 1) Original files are the floor — the LLM's fix only ADDS/OVERWRITES.
    merged = {**original, **fixed}
    # 2) The baked kit always wins — un-clobberable, LLM-independent.
    merged.update(PREMIUM_SCAFFOLD_FILES)
    return merged


class OnCallRequest(BaseModel):
    project_id: str | None = None
    files: dict[str, str]
    error: str
    session_id: str | None = None  # ponytail: kept for backward compat, ignored for ownership


class OnCallResponse(BaseModel):
    project_id: str
    files: dict[str, str]


@router.post("", response_model=OnCallResponse)
def oncall(
    req: OnCallRequest,
    current_user: User = Depends(get_current_user),
) -> OnCallResponse:
    if not req.error.strip():
        raise HTTPException(status_code=400, detail="error must not be empty")
    if not req.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    raw = chat(
        oncall_prompt(req.files, req.error),
        chain=CODER_CHAIN,
        system=CODER_SYSTEM_PROMPT,
        max_tokens=8192,
    )
    parsed = parse_multi_file_response(raw, strip_code_fences)
    fixed_files = normalize_files(parsed, detect_framework(req.files))

    # ponytail: on a premium app, PRESERVE the baked scaffold + any generated files
    # the LLM didn't reproduce — never let an autofix strip /ui/*, /lib/format.js or
    # /data/mock.js (that destroys the app). Non-premium apps are unaffected.
    if _is_premium_shaped(req.files):
        fixed_files = _preserve_premium_scaffold(req.files, fixed_files)

    # ponytail: brief stored as the error string (truncated) so the project row is meaningful
    brief = f"OnCall fix: {req.error[:120]}"
    project_id = _upsert_project(req.project_id, current_user.id, brief, fixed_files, source="oncall")
    return OnCallResponse(project_id=project_id, files=fixed_files)
