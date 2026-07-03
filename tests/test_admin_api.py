"""AI-logs admin endpoint — SUPER_ADMIN only."""
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.dependencies import get_current_user

client = TestClient(app)


def _override(role):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uuid.uuid4(), email="a@b.c", role=role
    )


def teardown_function():
    app.dependency_overrides.pop(get_current_user, None)


def test_ai_logs_non_admin_404():
    _override("user")
    r = client.get("/api/admin/ai-logs")
    assert r.status_code == 404


def test_ai_logs_super_admin_ok():
    _override("SUPER_ADMIN")
    r = client.get("/api/admin/ai-logs?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.real_auth
def test_ai_logs_unauth_401():
    r = client.get("/api/admin/ai-logs")
    assert r.status_code == 401
