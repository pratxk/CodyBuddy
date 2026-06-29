"""
Tests for POST /api/enhance — network/DB-free.
Auth is bypassed via conftest override; the LLM (chat) and DB (SessionLocal) are mocked.
"""
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

_SAMPLE_FILES = {"/App.js": "export default function App(){return <div>Hi</div>;}"}

# VibeEngineer now emits a REPLY block first, then the FILE blocks.
_LLM_WITH_REPLY = """\
=== REPLY ===
Done — switched the palette to a calm dark teal and added a hover lift to the cards. Want me to animate the chart next?
=== FILE: /App.js ===
export default function App() { return <div>Updated</div>; }
=== FILE: /styles.css ===
body { margin: 0; }
"""

# Older-style payload with no REPLY block — reply must fall back.
_LLM_NO_REPLY = """\
=== FILE: /App.js ===
export default function App() { return <div>Updated</div>; }
"""


def _mock_db_session():
    row = MagicMock()
    row.id = uuid.uuid4()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", row.id))
    return session


def test_enhance_returns_reply_and_files():
    session = _mock_db_session()
    with (
        patch("api.enhance.chat", return_value=_LLM_WITH_REPLY),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": _SAMPLE_FILES, "instruction": "use a calm dark teal palette"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"].startswith("Done — switched the palette")
    # files parsed + normalized (package.json auto-added by normalize_files)
    assert "/App.js" in body["files"]
    assert "/styles.css" in body["files"]
    assert "/package.json" in body["files"]
    # the REPLY block must be stripped out of the files map
    assert "REPLY" not in "".join(body["files"].values())
    assert "project_id" in body


def test_enhance_reply_falls_back_when_absent():
    session = _mock_db_session()
    with (
        patch("api.enhance.chat", return_value=_LLM_NO_REPLY),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": _SAMPLE_FILES, "instruction": "tweak it"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "Applied your changes."
    assert "/App.js" in body["files"]


def test_enhance_validation_blank_instruction():
    r = client.post("/api/enhance", json={"files": _SAMPLE_FILES, "instruction": "   "})
    assert r.status_code == 400


def test_enhance_validation_empty_files():
    r = client.post("/api/enhance", json={"files": {}, "instruction": "do something"})
    assert r.status_code == 400
