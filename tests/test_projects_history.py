"""
Tests for session-history persistence:
  - GET /api/projects/{id} includes chat + oncall_log (empty by default)
  - GET /api/projects (summaries) does NOT include chat / oncall_log
  - PUT /api/projects/{id}/history persists both arrays
  - PUT is owner-gated (404 not-found, 404 wrong-user)
  - PUT without auth returns 401
  - PUT rejects non-list chat or oncall_log with 422

Auth is bypassed via conftest.override_auth (FAKE_USER_ID = aaaabbbb-...).
"""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from auth.dependencies import get_current_user

client = TestClient(app)

_FAKE_USER_ID = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb")
_PROJECT_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
_PROJECT_ID_STR = str(_PROJECT_ID)

_CHAT_ENTRIES = [
    {"id": "c1", "agent": "vibe", "role": "user", "text": "hello", "at": "2026-01-01T00:00:00Z"}
]
_ONCALL_ENTRIES = [
    {"id": "o1", "at": "2026-01-01T00:00:00Z", "error": "err", "summary": "fixed", "files_changed": []}
]


def _make_project_row(user_id=_FAKE_USER_ID, chat=None, oncall_log=None):
    return SimpleNamespace(
        id=_PROJECT_ID,
        session_id="sess-test",
        user_id=user_id,
        title="Test Project",
        brief="a brief",
        files={"/App.js": "x"},
        chat=chat if chat is not None else [],
        oncall_log=oncall_log if oncall_log is not None else [],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


class _FakeDB:
    """Minimal SessionLocal context-manager mock."""

    def __init__(self, row=None, rows=None):
        self._row = row
        self._rows = rows or []
        self.committed = False
        self._get_row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def execute(self, *a, **kw):
        rows = self._rows

        class _Result:
            def scalars(self): return self
            def all(self): return rows

        return _Result()

    def get(self, model, pk):
        return self._get_row

    def delete(self, row):
        self.deleted = row

    def commit(self):
        self.committed = True


# ── GET /api/projects/{id} — chat + oncall_log included ──────────────────────


def test_get_project_includes_empty_history(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.get(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chat"] == []
    assert body["oncall_log"] == []


def test_get_project_includes_populated_history(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row(chat=_CHAT_ENTRIES, oncall_log=_ONCALL_ENTRIES)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.get(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chat"] == _CHAT_ENTRIES
    assert body["oncall_log"] == _ONCALL_ENTRIES


# ── GET /api/projects — summaries do NOT include history ─────────────────────


def test_projects_list_omits_history(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row(chat=_CHAT_ENTRIES, oncall_log=_ONCALL_ENTRIES)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(rows=[row]))
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    item = resp.json()[0]
    assert "chat" not in item
    assert "oncall_log" not in item


# ── PUT /api/projects/{id}/history ───────────────────────────────────────────


def test_put_history_persists_both_arrays(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    db = _FakeDB(row=row)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: db)
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": _CHAT_ENTRIES, "oncall_log": _ONCALL_ENTRIES},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert row.chat == _CHAT_ENTRIES
    assert row.oncall_log == _ONCALL_ENTRIES
    assert db.committed


def test_put_history_empty_arrays(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row(chat=_CHAT_ENTRIES, oncall_log=_ONCALL_ENTRIES)
    db = _FakeDB(row=row)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: db)
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": [], "oncall_log": []},
    )
    assert resp.status_code == 200
    assert row.chat == []
    assert row.oncall_log == []


def test_put_history_not_found(monkeypatch):
    import api.projects as proj_mod
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=None))
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": [], "oncall_log": []},
    )
    assert resp.status_code == 404


def test_put_history_wrong_user_returns_404(monkeypatch):
    import api.projects as proj_mod
    other_id = uuid.UUID("bbbbcccc-dddd-eeee-ffff-000011112222")
    row = _make_project_row(user_id=other_id)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": [], "oncall_log": []},
    )
    assert resp.status_code == 404


def test_put_history_invalid_uuid_returns_404(monkeypatch):
    resp = client.put(
        "/api/projects/not-a-uuid/history",
        json={"chat": [], "oncall_log": []},
    )
    assert resp.status_code == 404


@pytest.mark.real_auth
def test_put_history_unauthenticated_returns_401():
    """Without auth override, missing/invalid token → 401."""
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": [], "oncall_log": []},
    )
    assert resp.status_code == 401


# ── DELETE /api/projects/{id} — owner-gated session delete ───────────────────


def test_delete_project_owner_removes_row(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    db = _FakeDB(row=row)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: db)
    resp = client.delete(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert db.deleted is row
    assert db.committed


def test_delete_project_wrong_user_returns_404(monkeypatch):
    import api.projects as proj_mod
    other_id = uuid.UUID("bbbbcccc-dddd-eeee-ffff-000011112222")
    db = _FakeDB(row=_make_project_row(user_id=other_id))
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: db)
    resp = client.delete(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 404
    assert getattr(db, "deleted", None) is None


def test_delete_project_not_found_returns_404(monkeypatch):
    import api.projects as proj_mod
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=None))
    resp = client.delete(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 404


def test_delete_project_invalid_uuid_returns_404():
    resp = client.delete("/api/projects/not-a-uuid")
    assert resp.status_code == 404


@pytest.mark.real_auth
def test_delete_project_unauthenticated_returns_401():
    resp = client.delete(f"/api/projects/{_PROJECT_ID_STR}")
    assert resp.status_code == 401


def test_put_history_non_list_chat_returns_422(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": "not-a-list", "oncall_log": []},
    )
    assert resp.status_code == 422


def test_put_history_non_list_oncall_log_returns_422(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.put(
        f"/api/projects/{_PROJECT_ID_STR}/history",
        json={"chat": [], "oncall_log": {"key": "not-a-list"}},
    )
    assert resp.status_code == 422


# ── version history (snapshot on change + list + revert) ─────────────────────

def test_snapshot_version_caps_and_records(monkeypatch):
    from types import SimpleNamespace
    from api.enhance import snapshot_version, _MAX_VERSIONS
    row = SimpleNamespace(files={"/App.js": "v1"}, versions=[])
    snapshot_version(row, "enhance", "made it blue")
    assert len(row.versions) == 1
    assert row.versions[0]["source"] == "enhance"
    assert row.versions[0]["files"] == {"/App.js": "v1"}
    # cap
    row.versions = [{"id": str(i), "at": "x", "source": "e", "label": "", "files": {}} for i in range(_MAX_VERSIONS)]
    row.files = {"/App.js": "newest"}
    snapshot_version(row, "oncall", "fix")
    assert len(row.versions) == _MAX_VERSIONS
    assert row.versions[-1]["files"] == {"/App.js": "newest"}


def test_list_versions_newest_first(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    row.versions = [
        {"id": "a", "at": "2026-01-01T00:00:00Z", "source": "enhance", "label": "one", "files": {"/App.js": "1"}},
        {"id": "b", "at": "2026-01-02T00:00:00Z", "source": "oncall", "label": "two", "files": {"/App.js": "2"}},
    ]
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.get(f"/api/projects/{_PROJECT_ID_STR}/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert [v["id"] for v in body] == ["b", "a"]  # newest first
    assert "files" not in body[0]  # metadata only


def test_revert_restores_files_and_snapshots_current(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row()
    row.files = {"/App.js": "CURRENT"}
    row.versions = [{"id": "v1", "at": "x", "source": "enhance", "label": "old", "files": {"/App.js": "OLD"}}]
    db = _FakeDB(row=row)
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: db)
    resp = client.post(f"/api/projects/{_PROJECT_ID_STR}/revert", json={"version_id": "v1"})
    assert resp.status_code == 200
    assert resp.json()["files"] == {"/App.js": "OLD"}      # reverted
    assert row.files == {"/App.js": "OLD"}
    # current was snapshotted first (so revert is undoable)
    assert any(v["files"] == {"/App.js": "CURRENT"} for v in row.versions)


def test_revert_unknown_version_404(monkeypatch):
    import api.projects as proj_mod
    row = _make_project_row(); row.versions = []
    monkeypatch.setattr(proj_mod, "SessionLocal", lambda: _FakeDB(row=row))
    resp = client.post(f"/api/projects/{_PROJECT_ID_STR}/revert", json={"version_id": "nope"})
    assert resp.status_code == 404
