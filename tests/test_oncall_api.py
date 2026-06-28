"""
Tests for POST /api/oncall — network/DB-free.
"""
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

# Minimal valid files + LLM response fixture
_SAMPLE_FILES = {"/App.js": "export default function App(){return <div>{{}}</div>;}"}

_LLM_RESPONSE = """\
=== FILE: /App.js ===
export default function App() { return <div>Fixed</div>; }
=== FILE: /styles.css ===
body { margin: 0; }
"""


def _mock_db_session():
    """Return a mock context-manager DB session that silently does nothing."""
    row = MagicMock()
    row.id = uuid.uuid4()
    row.session_id = "sess-abc"

    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.get = MagicMock(return_value=None)  # no existing project
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", row.id))

    return session


def test_oncall_returns_fixed_files():
    """Happy path: mocked LLM returns a file block; response has project_id + files."""
    session = _mock_db_session()
    with (
        patch("api.oncall.chat", return_value=_LLM_RESPONSE),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/oncall",
            json={
                "files": _SAMPLE_FILES,
                "error": "Objects are not valid as a React child",
                "session_id": "sess-abc",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "project_id" in body
    assert "files" in body
    # normalize_files adds leading slash and /package.json
    assert "/App.js" in body["files"]
    assert "/styles.css" in body["files"]
    assert "/package.json" in body["files"]


def test_oncall_normalize_runs():
    """Paths without leading slash must be normalized to have one."""
    no_slash_files = {"App.js": "export default function App(){return null;}"}
    session = _mock_db_session()
    with (
        patch("api.oncall.chat", return_value=_LLM_RESPONSE),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/oncall",
            json={
                "files": no_slash_files,
                "error": "some error",
                "session_id": "sess-xyz",
            },
        )
    assert r.status_code == 200
    assert "/App.js" in r.json()["files"]


def test_oncall_validation_blank_error():
    r = client.post(
        "/api/oncall",
        json={"files": _SAMPLE_FILES, "error": "   ", "session_id": "sess-abc"},
    )
    assert r.status_code == 400
    assert "error" in r.json()["detail"].lower()


def test_oncall_validation_blank_session_id():
    r = client.post(
        "/api/oncall",
        json={"files": _SAMPLE_FILES, "error": "some error", "session_id": ""},
    )
    assert r.status_code == 400
    assert "session_id" in r.json()["detail"].lower()


def test_oncall_validation_empty_files():
    r = client.post(
        "/api/oncall",
        json={"files": {}, "error": "some error", "session_id": "sess-abc"},
    )
    assert r.status_code == 400
    assert "files" in r.json()["detail"].lower()
