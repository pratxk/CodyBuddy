"""
Admin observability endpoints — SUPER_ADMIN only.

GET /api/admin/ai-logs — recent LLM calls across all agents (provider, model,
latency, ok, prompt/response previews) for an in-app "AI Logs" viewer.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from auth.dependencies import get_current_user
from db.database import SessionLocal
from db.models import AiCallLog, User

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_super_admin(user: User) -> None:
    if getattr(user, "role", "") != "SUPER_ADMIN":
        # 404 (not 403) — don't advertise the endpoint's existence to non-admins.
        raise HTTPException(status_code=404, detail="Not found")


class AiLogRow(BaseModel):
    id: str
    at: str
    agent: str
    kind: str
    provider: str
    model: str
    latency_ms: int
    ok: bool
    error: str
    prompt: str
    response: str


@router.get("/ai-logs", response_model=list[AiLogRow])
def ai_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
) -> list[AiLogRow]:
    """Recent LLM calls, newest first. SUPER_ADMIN only."""
    _require_super_admin(current_user)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    with SessionLocal() as db:
        rows = db.execute(
            select(AiCallLog).order_by(AiCallLog.at.desc()).limit(limit).offset(offset)
        ).scalars().all()
    return [
        AiLogRow(
            id=str(r.id), at=r.at.isoformat() if r.at else "", agent=r.agent, kind=r.kind,
            provider=r.provider, model=r.model, latency_ms=r.latency_ms, ok=r.ok,
            error=r.error, prompt=r.prompt, response=r.response,
        )
        for r in rows
    ]
