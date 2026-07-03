"""
SQLAlchemy ORM models for CodyBuddy.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    # ponytail: allowlist-driven role; "user" by default, "SUPER_ADMIN" for allowlisted emails.
    # Existing rows on Neon need scripts/migrate_add_role.sql (create_all won't ALTER).
    role: Mapped[str] = mapped_column(String, default="user", server_default="user", nullable=False)
    # ponytail: GitHub PAT stored ENCRYPTED (Fernet via auth/crypto.py) — never plaintext.
    # github_login is cached alongside so /me doesn't call GitHub on every request.
    # Existing Neon rows need scripts/migrate_add_github_token.sql (create_all won't ALTER).
    github_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_login: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    files: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # ponytail: which framework this app was generated as ("react" | "static" | "nextjs").
    # Existing Neon rows need scripts/migrate_add_framework.sql (create_all won't ALTER).
    framework: Mapped[str] = mapped_column(
        String, nullable=False, default="react", server_default="react"
    )
    # ponytail: session-history columns; existing Neon rows need
    # scripts/migrate_add_session_history.sql (create_all won't ALTER).
    chat: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    oncall_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # ponytail: version history — a capped list of prior file snapshots so a user
    # can revert when a change (OnCall/enhance/edit) messes the app up. Each entry:
    # {id, at, source, label, files}. Existing Neon rows need
    # scripts/migrate_add_versions.sql (create_all won't ALTER).
    versions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    # ponytail: index=True on the column handles ix_projects_session_id; no __table_args__ needed


class AiCallLog(Base):
    """Observability — one row per LLM call across all agents. Best-effort
    (writes never break a build). SUPER_ADMIN-only viewer reads recent rows."""

    __tablename__ = "ai_call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    agent: Mapped[str] = mapped_column(String, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String, nullable=False, default="chat")
    provider: Mapped[str] = mapped_column(String, nullable=False, default="")
    model: Mapped[str] = mapped_column(String, nullable=False, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
