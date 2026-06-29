"""
Tests for GitHub integration endpoints + /api/auth/me github field.
Network-free: GitHub HTTP (validate_token) and DB are mocked. The PAT is never returned.
"""
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth import crypto
from auth.dependencies import get_current_user
from auth.utils import create_access_token
from db.database import get_db

client = TestClient(app)


def _override_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


@contextmanager
def _db_with_user(user):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.commit = MagicMock()

    def _get():
        yield db

    app.dependency_overrides[get_db] = _get
    try:
        yield db
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── PUT /api/me/integrations/github ─────────────────────────────────────────────


def test_connect_github_stores_encrypted_and_returns_login():
    user = SimpleNamespace(id=uuid.uuid4(), email="u@x.com", name="U", role="user",
                           github_token_enc=None, github_login=None)
    _override_user(user)
    with _db_with_user(user):
        with patch("api.integrations.github_client.validate_token", return_value="octocat"):
            r = client.put("/api/me/integrations/github", json={"token": "ghp_realtoken123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"connected": True, "login": "octocat"}
    # token never echoed
    assert "ghp_realtoken123" not in r.text
    # stored value is encrypted, and round-trips back to the original
    assert user.github_token_enc and user.github_token_enc != "ghp_realtoken123"
    assert crypto.decrypt(user.github_token_enc) == "ghp_realtoken123"
    assert user.github_login == "octocat"


def test_connect_github_invalid_token_returns_400():
    user = SimpleNamespace(id=uuid.uuid4(), email="u@x.com", name="U", role="user",
                           github_token_enc=None, github_login=None)
    _override_user(user)
    with _db_with_user(user):
        with patch("api.integrations.github_client.validate_token",
                   side_effect=ValueError("Invalid GitHub token")):
            r = client.put("/api/me/integrations/github", json={"token": "bad"})
    assert r.status_code == 400
    assert user.github_token_enc is None  # nothing stored on failure


def test_connect_github_blank_token_returns_400():
    user = SimpleNamespace(id=uuid.uuid4(), email="u@x.com", name="U", role="user",
                           github_token_enc=None, github_login=None)
    _override_user(user)
    with _db_with_user(user):
        r = client.put("/api/me/integrations/github", json={"token": "   "})
    assert r.status_code == 400


# ── DELETE /api/me/integrations/github ──────────────────────────────────────────


def test_disconnect_github_clears():
    user = SimpleNamespace(id=uuid.uuid4(), email="u@x.com", name="U", role="user",
                           github_token_enc=crypto.encrypt("ghp_x"), github_login="octocat")
    _override_user(user)
    with _db_with_user(user):
        r = client.delete("/api/me/integrations/github")
    assert r.status_code == 200, r.text
    assert r.json() == {"connected": False}
    assert user.github_token_enc is None
    assert user.github_login is None


# ── /api/auth/me github field ───────────────────────────────────────────────────


@pytest.mark.real_auth
def test_me_includes_github_connected_and_login():
    uid = uuid.uuid4()
    user = SimpleNamespace(id=uid, email="me@x.com", name="Me",
                           github_token_enc=crypto.encrypt("ghp_secret"), github_login="octocat")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    def _get():
        yield db

    app.dependency_overrides[get_db] = _get
    try:
        token = create_access_token(str(uid), "me@x.com")
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["github"] == {"connected": True, "login": "octocat"}
    # the encrypted token must never appear in the /me payload
    assert user.github_token_enc not in r.text
    assert "ghp_secret" not in r.text


@pytest.mark.real_auth
def test_me_github_disconnected_when_no_token():
    uid = uuid.uuid4()
    user = SimpleNamespace(id=uid, email="me@x.com", name="Me",
                           github_token_enc=None, github_login=None)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user

    def _get():
        yield db

    app.dependency_overrides[get_db] = _get
    try:
        token = create_access_token(str(uid), "me@x.com")
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 200, r.text
    assert r.json()["github"] == {"connected": False, "login": None}
