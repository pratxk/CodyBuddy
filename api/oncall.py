"""
OnCallAgent endpoint — POST /api/oncall.

Auto-repairs a runtime/compile error in the live app.

Premium apps get a SURGICAL repair: OnCall sees ONLY the file(s) the error names
(+ the entry for context) and is told to make the SMALLEST possible fix, emitting
only the changed file(s) — so one stray comma can't cascade into a full rewrite
that breaks unrelated code. The frozen kit (/ui, /lib, /styles.css, package.json)
is never touched. Standard apps keep the whole-file-set repair (they're small).
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent.llm import CODER_CHAIN, chat, strip_code_fences
from agent.premium_scaffold import is_premium_shaped, preserve_premium_scaffold
from agent.prompts import CODER_SYSTEM_PROMPT, oncall_prompt, oncall_prompt_scoped
from agent.scaffold import (detect_framework, normalize_files,
                           parse_multi_file_response)
from api.enhance import _upsert_project
from auth.dependencies import get_current_user
from db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/oncall", tags=["oncall"])

# File paths referenced anywhere in an error string (with or without a leading slash).
_PATH_RE = re.compile(r"/?(?:[\w.-]+/)*[\w.-]+\.(?:jsx?|tsx?|css)")
# The frozen kit — never sent to / repaired by OnCall.
_FROZEN = ("/ui/", "/lib/")


def _relevant_files(files: dict[str, str], error: str) -> dict[str, str]:
    """The editable file(s) implicated by the error — so OnCall fixes ONLY those,
    not all ~22 files. Matches paths/basenames named in the error against the app's
    files; always includes the entry (/App.js) for context. Falls back to the whole
    editable surface (App + views + data, NOT the frozen kit) when nothing matches."""
    editable = {p: c for p, c in files.items()
                if not p.startswith(_FROZEN) and p not in ("/styles.css", "/package.json")}
    named = {m.group(0).lstrip("/") for m in _PATH_RE.finditer(error or "")}
    hit = {p: c for p, c in editable.items()
           if p.lstrip("/") in named or p.rsplit("/", 1)[-1] in named}
    if "/App.js" in editable:
        hit["/App.js"] = editable["/App.js"]
    return hit or editable


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

    if is_premium_shaped(req.files):
        # SURGICAL premium repair: show only the implicated file(s), fix minimally,
        # emit only the changed file(s), then merge over the app + re-freeze the kit.
        relevant = _relevant_files(req.files, req.error)
        raw = chat(
            oncall_prompt_scoped(relevant, req.error),
            chain=CODER_CHAIN, system=CODER_SYSTEM_PROMPT, max_tokens=8192, agent="oncall",
        )
        changed = parse_multi_file_response(raw, strip_code_fences)
        merged = normalize_files({**req.files, **changed}, "react")
        fixed_files = preserve_premium_scaffold(req.files, merged)
    else:
        raw = chat(
            oncall_prompt(req.files, req.error),
            chain=CODER_CHAIN, system=CODER_SYSTEM_PROMPT, max_tokens=8192, agent="oncall",
        )
        parsed = parse_multi_file_response(raw, strip_code_fences)
        fixed_files = normalize_files(parsed, detect_framework(req.files))

    brief = f"OnCall fix: {req.error[:120]}"
    project_id = _upsert_project(req.project_id, current_user.id, brief, fixed_files, source="oncall")
    return OnCallResponse(project_id=project_id, files=fixed_files)
