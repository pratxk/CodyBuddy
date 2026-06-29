"""
SQLAlchemy ORM models for CodyBuddy.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    # ponytail: index=True on the column handles ix_projects_session_id; no __table_args__ needed
