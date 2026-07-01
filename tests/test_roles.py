"""
Role allowlist tests — the SUPER_ADMIN allowlist must be authoritative, and
ensure_role must persist the upgrade so downstream gates (premium generation)
see the right role on every request, not just at login.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from auth.roles import resolve_role, ensure_role, SUPER_ADMIN_EMAILS


def test_resolve_role_allowlisted_email_is_super_admin():
    email = next(iter(SUPER_ADMIN_EMAILS))
    assert resolve_role(email) == "SUPER_ADMIN"
    assert resolve_role(email.upper()) == "SUPER_ADMIN"  # case-insensitive


def test_resolve_role_regular_email_is_user():
    assert resolve_role("nobody@example.com") == "user"
    assert resolve_role("") == "user"


def test_ensure_role_upgrades_and_persists_stale_super_admin():
    """The exact bug: a SUPER_ADMIN-allowlisted user whose DB row still says
    role='user' must be upgraded AND committed."""
    email = next(iter(SUPER_ADMIN_EMAILS))
    user = SimpleNamespace(email=email, role="user")
    db = MagicMock()
    role = ensure_role(user, db)
    assert role == "SUPER_ADMIN"
    assert user.role == "SUPER_ADMIN"
    db.commit.assert_called_once()


def test_ensure_role_idempotent_no_write_when_already_super_admin():
    email = next(iter(SUPER_ADMIN_EMAILS))
    user = SimpleNamespace(email=email, role="SUPER_ADMIN")
    db = MagicMock()
    assert ensure_role(user, db) == "SUPER_ADMIN"
    db.commit.assert_not_called()


def test_ensure_role_regular_user_stays_user_no_write():
    user = SimpleNamespace(email="nobody@example.com", role="user")
    db = MagicMock()
    assert ensure_role(user, db) == "user"
    db.commit.assert_not_called()


def test_get_current_user_applies_allowlist_role(monkeypatch):
    """get_current_user must upgrade an allowlisted user's role so the premium
    gate honors it on generation requests (not just /me)."""
    import auth.dependencies as deps

    email = next(iter(SUPER_ADMIN_EMAILS))
    user = SimpleNamespace(id="u1", email=email, role="user")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    monkeypatch.setattr(deps, "decode_access_token", lambda t: {"sub": "u1"})

    returned = deps.get_current_user(authorization="Bearer tok", db=db)
    assert returned.role == "SUPER_ADMIN"
    db.commit.assert_called_once()
