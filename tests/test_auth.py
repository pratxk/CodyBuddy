"""
Auth module tests — DB-free (get_db is mocked per test).
real_auth marker disables conftest get_current_user override for specific tests.
"""
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.utils import create_access_token, decode_access_token, hash_password, verify_password
from db.database import get_db

client = TestClient(app)


# ── utils unit tests (no HTTP, no DB) ─────────────────────────────────────────


def test_hash_is_not_plain():
    hashed = hash_password("secret123")
    assert hashed != "secret123"


def test_verify_correct_password():
    hashed = hash_password("correct")
    assert verify_password("correct", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_jwt_round_trip():
    uid = str(uuid.uuid4())
    token = create_access_token(uid, "u@test.com")
    payload = decode_access_token(token)
    assert payload["sub"] == uid
    assert payload["email"] == "u@test.com"


# ── DB mock helpers ────────────────────────────────────────────────────────────


def _make_db(existing_user=None, user_by_google=None, user_by_email=None):
    """Mock DB session that returns controlled query results."""
    db = MagicMock()
    fake_id = uuid.uuid4()

    def _add(obj):
        # Set id so create_access_token can use it
        obj.id = fake_id

    db.add = MagicMock(side_effect=_add)
    db.commit = MagicMock()
    db.refresh = MagicMock()

    def _query_first(*args, **kwargs):
        return existing_user

    # Default: all queries return existing_user
    db.query.return_value.filter.return_value.first = MagicMock(side_effect=_query_first)
    return db, fake_id


@contextmanager
def _db_override(db):
    def _get():
        yield db

    app.dependency_overrides[get_db] = _get
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── /signup ────────────────────────────────────────────────────────────────────


def test_signup_returns_token_and_user():
    db, fake_id = _make_db(existing_user=None)
    # After add sets id, refresh should make email/name accessible
    captured = {}

    def _add(obj):
        obj.id = fake_id
        captured["user"] = obj

    db.add = MagicMock(side_effect=_add)

    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "new@example.com",
            "password": "password123",
            "name": "New User",
        })
    assert r.status_code == 201, r.text
    body = r.json()
    assert "token" in body
    assert body["user"]["email"] == "new@example.com"
    # Token must be decodable
    payload = decode_access_token(body["token"])
    assert payload["email"] == "new@example.com"


def test_signup_super_admin_email_gets_super_admin_role():
    db, fake_id = _make_db(existing_user=None)
    db.query.return_value.filter.return_value.first.return_value = None
    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "proff.pratiksingh@gmail.com",
            "password": "password123",
        })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "SUPER_ADMIN"


def test_signup_regular_email_gets_user_role():
    db, fake_id = _make_db(existing_user=None)
    db.query.return_value.filter.return_value.first.return_value = None
    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "regular@example.com",
            "password": "password123",
        })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "user"


def test_signup_super_admin_email_is_case_insensitive():
    db, fake_id = _make_db(existing_user=None)
    db.query.return_value.filter.return_value.first.return_value = None
    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "Proff.PratikSingh@Gmail.com",
            "password": "password123",
        })
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "SUPER_ADMIN"


def test_signup_hashes_password():
    db, fake_id = _make_db(existing_user=None)
    captured = {}

    def _add(obj):
        obj.id = fake_id
        captured["hashed"] = obj.hashed_password

    db.add = MagicMock(side_effect=_add)
    db.query.return_value.filter.return_value.first.return_value = None

    with _db_override(db):
        client.post("/api/auth/signup", json={
            "email": "x@x.com", "password": "plaintext1",
        })
    assert captured.get("hashed") is not None
    assert captured["hashed"] != "plaintext1"
    assert verify_password("plaintext1", captured["hashed"])


def test_signup_duplicate_email_returns_409():
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.email = "taken@example.com"
    db, _ = _make_db(existing_user=existing)

    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "taken@example.com",
            "password": "password123",
        })
    assert r.status_code == 409


def test_signup_short_password_returns_400():
    db, _ = _make_db(existing_user=None)
    with _db_override(db):
        r = client.post("/api/auth/signup", json={
            "email": "x@x.com", "password": "short",
        })
    assert r.status_code == 400


# ── /login ─────────────────────────────────────────────────────────────────────


def test_login_valid_credentials_returns_token():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.name = "User"
    user.hashed_password = hash_password("mypassword")
    db, _ = _make_db(existing_user=user)

    with _db_override(db):
        r = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "mypassword",
        })
    assert r.status_code == 200, r.text
    assert "token" in r.json()


def test_login_wrong_password_returns_401():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "user@example.com"
    user.hashed_password = hash_password("correct")
    db, _ = _make_db(existing_user=user)

    with _db_override(db):
        r = client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "wrong",
        })
    assert r.status_code == 401


def test_login_unknown_email_returns_401():
    db, _ = _make_db(existing_user=None)
    with _db_override(db):
        r = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
    assert r.status_code == 401


# ── /google ────────────────────────────────────────────────────────────────────


def test_google_without_client_id_returns_503(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    r = client.post("/api/auth/google", json={"id_token": "fake"})
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"].lower()


def test_google_with_mocked_token_upserts_user(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")

    fake_idinfo = {
        "sub": "google-uid-123",
        "email": "guser@gmail.com",
        "name": "Google User",
    }

    db, fake_id = _make_db(existing_user=None)
    # Both google_id and email queries return None (new user)
    db.query.return_value.filter.return_value.first.return_value = None

    captured = {}

    def _add(obj):
        obj.id = fake_id
        captured["user"] = obj

    db.add = MagicMock(side_effect=_add)

    with _db_override(db):
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value=fake_idinfo):
            r = client.post("/api/auth/google", json={"id_token": "valid-token"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert "token" in body
    assert body["user"]["email"] == "guser@gmail.com"


# ── /me ────────────────────────────────────────────────────────────────────────


@pytest.mark.real_auth
def test_me_without_token_returns_401():
    r = client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.real_auth
def test_me_with_valid_token_returns_user():
    fake_uid = uuid.uuid4()
    user = MagicMock()
    user.id = fake_uid
    user.email = "me@example.com"
    user.name = "Me"
    db, _ = _make_db(existing_user=user)
    db.query.return_value.filter.return_value.first.return_value = user

    token = create_access_token(str(fake_uid), "me@example.com")

    with _db_override(db):
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["role"] == "user"


@pytest.mark.real_auth
def test_me_returns_super_admin_role_for_allowlisted_email():
    fake_uid = uuid.uuid4()
    user = MagicMock()
    user.id = fake_uid
    user.email = "proff.pratiksingh@gmail.com"
    user.name = "Admin"
    db, _ = _make_db(existing_user=user)
    db.query.return_value.filter.return_value.first.return_value = user

    token = create_access_token(str(fake_uid), "proff.pratiksingh@gmail.com")
    with _db_override(db):
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "SUPER_ADMIN"


# ── protected endpoint requires auth ──────────────────────────────────────────


@pytest.mark.real_auth
def test_protected_endpoint_returns_401_without_token():
    r = client.post("/api/intake", json={"prompt": "hello"})
    assert r.status_code == 401
