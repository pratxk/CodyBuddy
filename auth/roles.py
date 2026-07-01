"""
Role resolution — the SUPER_ADMIN allowlist is the single source of truth.

Lives in the `auth` layer (not `api`) so BOTH the auth endpoints and the
`get_current_user` dependency can apply it. Previously the allowlist upgrade
only ran during login/`/me`, so a request authenticated with a token whose DB
row still said `role='user'` (e.g. a SUPER_ADMIN email that logged in before the
upgrade persisted) was treated as a normal user by downstream gates like the
premium generation flow. Applying it in `get_current_user` makes every
authenticated request authoritative.
"""
import os

from sqlalchemy.orm import Session

from db.models import User

# ponytail: small allowlist drives the SUPER_ADMIN role (env-overridable, comma-separated).
SUPER_ADMIN_EMAILS: set[str] = {
    e.strip().lower()
    for e in os.environ.get("SUPER_ADMIN_EMAILS", "proff.pratiksingh@gmail.com").split(",")
    if e.strip()
}


def resolve_role(email: str) -> str:
    """Role is fully determined by the email allowlist (case-insensitive)."""
    return "SUPER_ADMIN" if (email or "").lower() in SUPER_ADMIN_EMAILS else "user"


def ensure_role(user: User, db: Session) -> str:
    """Set the user's role from the allowlist, persisting an upgrade to
    SUPER_ADMIN once. Idempotent: after the first upgrade it only reads."""
    role = resolve_role(user.email)
    if getattr(user, "role", None) != role and role == "SUPER_ADMIN":
        user.role = role
        db.commit()
    return role
