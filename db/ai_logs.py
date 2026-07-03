"""Best-effort AI-call logging for observability.

Every LLM call across the agents records one row (provider, model, latency,
prompt/response previews). Writes are BEST-EFFORT — a logging failure must never
break a build/edit — and previews are truncated to keep the table small.
"""
import logging

logger = logging.getLogger(__name__)

_PREVIEW_MAX = 8000  # chars kept per prompt/response


def _truncate(s: str) -> str:
    s = s or ""
    return s if len(s) <= _PREVIEW_MAX else s[:_PREVIEW_MAX] + f"\n…[+{len(s) - _PREVIEW_MAX} chars]"


def log_ai_call(*, agent: str, kind: str, provider: str, model: str,
                latency_ms: int, ok: bool, error: str = "",
                prompt: str = "", response: str = "") -> None:
    """Insert one AI-call log row. Never raises."""
    try:
        from db.database import SessionLocal
        from db.models import AiCallLog
        with SessionLocal() as db:
            db.add(AiCallLog(
                agent=agent or "", kind=kind or "chat",
                provider=provider or "", model=model or "",
                latency_ms=int(latency_ms), ok=bool(ok), error=_truncate(error),
                prompt=_truncate(prompt), response=_truncate(response),
            ))
            db.commit()
    except Exception as exc:  # noqa: BLE001 — logging must never break a build
        logger.debug("ai-call log write skipped: %s", exc)
