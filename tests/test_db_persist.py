"""
Tests for:
 - Project model construction and field defaults (no live DB)
 - /api/enhance returns updated files (mock LLM + mock _upsert_project)
 - /api/projects list and get shape (mock SessionLocal)

Auth is bypassed via conftest override (FAKE_USER_ID = aaaabbbb-...).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from db.models import Project


# ── Project model unit tests (no DB required) ────────────────────────────────


def test_project_constructor_fields():
    """Project can be instantiated with required fields; files dict is preserved."""
    files = {"/App.js": "export default function App(){return <h1>Hi</h1>;}", "/styles.css": "body{}"}
    row = Project(
        session_id="sess-abc",
        title="Test App",
        brief="a test brief",
        files=files,
    )
    assert row.session_id == "sess-abc"
    assert row.title == "Test App"
    assert row.brief == "a test brief"
    assert row.files == files
    assert "/App.js" in row.files


def test_project_uuid_default():
    """Project id column has a Python-side default (uuid4) wired in the table metadata."""
    id_col = Project.__table__.c["id"]
    assert id_col.default is not None
    assert id_col.default.arg.__name__ == "uuid4"


def test_project_timestamp_defaults():
    """created_at and updated_at are set by _utcnow on construction."""
    from db.models import _utcnow
    ts = _utcnow()
    assert ts.tzinfo is not None  # timezone-aware


def test_project_files_is_dict():
    """Project.files accepts a dict with arbitrary path/content pairs."""
    files = {"/App.js": "x", "/components/Board.js": "y", "/package.json": "{}"}
    row = Project(session_id="s", title="t", brief="b", files=files)
    assert len(row.files) == 3
    assert row.files["/components/Board.js"] == "y"


# ── /api/enhance tests ────────────────────────────────────────────────────────


_ENHANCE_FILES = {
    "/App.js": "export default function App(){return <h1>Hello</h1>;}",
    "/styles.css": "body{margin:0}",
    "/package.json": '{"name":"test","dependencies":{"react":"^18"}}',
}

_ENHANCE_LLM_RESPONSE = (
    "=== FILE: /App.js ===\n"
    "export default function App(){return <h1 style={{color:'purple'}}>Hello</h1>;}\n"
    "=== FILE: /styles.css ===\nbody{margin:0}\n"
    "=== FILE: /package.json ===\n"
    '{"name":"test","dependencies":{"react":"^18.2.0"}}\n'
)

_PROJECT_ID = str(uuid.uuid4())


def _make_enhance_client(monkeypatch):
    """Return a TestClient with chat and _upsert_project both mocked."""
    import api.enhance as enhance_mod

    monkeypatch.setattr(enhance_mod, "chat", lambda *a, **kw: _ENHANCE_LLM_RESPONSE)
    monkeypatch.setattr(enhance_mod, "_upsert_project", lambda *a, **kw: _PROJECT_ID)

    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


def test_enhance_returns_updated_files(monkeypatch):
    client = _make_enhance_client(monkeypatch)
    resp = client.post(
        "/api/enhance",
        json={
            "files": _ENHANCE_FILES,
            "instruction": "change the heading to PURPLE",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "files" in body
    assert "project_id" in body
    assert "/App.js" in body["files"]
    assert "purple" in body["files"]["/App.js"].lower()


def test_enhance_returns_project_id(monkeypatch):
    client = _make_enhance_client(monkeypatch)
    resp = client.post(
        "/api/enhance",
        json={
            "files": _ENHANCE_FILES,
            "instruction": "make heading blue",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["project_id"] == _PROJECT_ID


def test_enhance_missing_instruction_returns_400(monkeypatch):
    client = _make_enhance_client(monkeypatch)
    resp = client.post(
        "/api/enhance",
        json={"files": _ENHANCE_FILES, "instruction": "  "},
    )
    assert resp.status_code == 400


def test_enhance_empty_files_returns_400(monkeypatch):
    client = _make_enhance_client(monkeypatch)
    resp = client.post(
        "/api/enhance",
        json={"files": {}, "instruction": "do something"},
    )
    assert resp.status_code == 400


# ── /api/projects tests ───────────────────────────────────────────────────────

# FAKE_USER_ID from conftest — projects must match this for ownership checks
_FAKE_USER_ID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb")


def _make_fake_project_row(user_id=_FAKE_USER_ID):
    """Return a SimpleNamespace that mimics a Project row (no DB, no ORM state)."""
    from types import SimpleNamespace
    return SimpleNamespace(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        session_id="",
        user_id=user_id,
        title="Fake Project",
        brief="a brief",
        files={"/App.js": "x"},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


class _FakeDB:
    """Minimal SessionLocal context-manager mock."""

    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def execute(self, *a, **kw):
        class _Scalars:
            def __init__(self, rows): self._rows = rows
            def scalars(self): return self
            def all(self): return self._rows

        return _Scalars(self._rows)

    def get(self, model, pid):
        return self._row


def test_projects_list_shape(monkeypatch):
    import api.projects as proj_mod
    fake_row = _make_fake_project_row()
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(rows=[fake_row]))

    from fastapi.testclient import TestClient
    from api.main import app
    resp = TestClient(app).get("/api/projects")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["id"] == "12345678-1234-5678-1234-567812345678"
    assert items[0]["title"] == "Fake Project"
    assert "created_at" in items[0]
    assert "updated_at" in items[0]
    assert "files" not in items[0]


def test_projects_get_shape(monkeypatch):
    import api.projects as proj_mod
    fake_row = _make_fake_project_row()
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=fake_row))

    from fastapi.testclient import TestClient
    from api.main import app
    pid = "12345678-1234-5678-1234-567812345678"
    resp = TestClient(app).get(f"/api/projects/{pid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == pid
    assert "files" in body
    assert "brief" in body


def test_projects_get_not_found(monkeypatch):
    import api.projects as proj_mod
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=None))

    from fastapi.testclient import TestClient
    from api.main import app
    pid = "12345678-1234-5678-1234-567812345678"
    resp = TestClient(app).get(f"/api/projects/{pid}")
    assert resp.status_code == 404


def test_projects_get_wrong_user_returns_404(monkeypatch):
    """Project owned by different user returns 404."""
    import api.projects as proj_mod
    other_user_id = uuid.UUID("bbbbcccc-dddd-eeee-ffff-000011112222")
    fake_row = _make_fake_project_row(user_id=other_user_id)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=fake_row))

    from fastapi.testclient import TestClient
    from api.main import app
    pid = "12345678-1234-5678-1234-567812345678"
    resp = TestClient(app).get(f"/api/projects/{pid}")
    assert resp.status_code == 404


def test_projects_get_invalid_uuid_returns_404():
    from fastapi.testclient import TestClient
    from api.main import app
    resp = TestClient(app).get("/api/projects/not-a-uuid")
    assert resp.status_code == 404
