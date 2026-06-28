"""
IntakeAgent endpoint — POST /api/intake.

Self-gating: decides whether a build prompt is specific enough to build directly.
If not, asks ONE adaptive clarifying question at a time (with selectable options)
until it has enough context, then emits a consolidated build brief.

Stateless: the FE passes the full Q&A history on every call. No DB writes.
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.llm import PLANNER_CHAIN, chat_structured
from agent.prompts import intake_prompt
from agent.states import IntakeStep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intake", tags=["intake"])

# ponytail: simple guard — never ask more than this many questions before forcing a build.
_MAX_HISTORY = 5


class QAPair(BaseModel):
    question: str
    answer: str


class IntakeRequest(BaseModel):
    prompt: str
    history: list[QAPair] = Field(default_factory=list)
    session_id: str | None = None


def _synthesize_brief(prompt: str, history: list[QAPair]) -> str:
    """Fold the original prompt + all answers into a single brief (cap fallback)."""
    answers = "; ".join(h.answer.strip() for h in history if h.answer.strip())
    return f"{prompt.strip()} ({answers})" if answers else prompt.strip()


@router.post("", response_model=IntakeStep)
def intake(req: IntakeRequest) -> IntakeStep:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    history = [h.model_dump() for h in req.history]
    step = chat_structured(
        intake_prompt(req.prompt, history),
        IntakeStep,
        chain=PLANNER_CHAIN,
        max_tokens=600,
    )

    # HARD CAP: stop asking after enough questions — force a build.
    # ponytail: simple guard against an indecisive model looping forever.
    if len(req.history) >= _MAX_HISTORY and not step.ready:
        brief = step.brief or _synthesize_brief(req.prompt, req.history)
        return IntakeStep(ready=True, brief=brief)

    # If the model says ready but gave no brief, fall back to the prompt.
    if step.ready and not (step.brief and step.brief.strip()):
        return IntakeStep(ready=True, brief=req.prompt.strip())

    return step
