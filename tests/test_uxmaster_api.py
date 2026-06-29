"""
Tests for POST /api/uxmaster — network/DB-free.
Auth is bypassed via conftest override; chat_vision and the DB (SessionLocal) are mocked.
"""
import uuid as _uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agent.llm import VISION_CHAIN
from api.main import app
from auth.dependencies import get_current_user

client = TestClient(app)

_SAMPLE_FILES = {"/App.js": "export default function App(){return <div>Hi</div>;}"}
_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANS"

_VISION_REPLY = """\
=== REPLY ===
The hero felt cramped and low-contrast — I added breathing room and a gradient header. Send me a fresh shot so I can confirm it landed.
=== VERIFY ===
true
=== FILE: /App.js ===
export default function App() { return <div>Updated</div>; }
=== FILE: /styles.css ===
body { margin: 0; }
"""


def _mock_db_session():
    row = MagicMock()
    row.id = _uuid.uuid4()
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", row.id))
    return session


def test_uxmaster_returns_reply_verify_and_files():
    session = _mock_db_session()
    with (
        patch("api.uxmaster.chat_vision", return_value=_VISION_REPLY),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/uxmaster",
            json={"files": _SAMPLE_FILES, "image": _DATA_URL, "instruction": "tighten the hero"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"].startswith("The hero felt cramped")
    assert body["needs_verification"] is True
    assert "/App.js" in body["files"]
    assert "/styles.css" in body["files"]
    assert "/package.json" in body["files"]  # normalize_files adds it
    assert "REPLY" not in "".join(body["files"].values())
    assert "VERIFY" not in "".join(body["files"].values())
    assert "project_id" in body


def test_uxmaster_400_when_image_missing():
    r = client.post("/api/uxmaster", json={"files": _SAMPLE_FILES, "image": "   "})
    assert r.status_code == 400


def test_uxmaster_400_when_image_not_data_url():
    r = client.post(
        "/api/uxmaster",
        json={"files": _SAMPLE_FILES, "image": "https://example.com/shot.png"},
    )
    assert r.status_code == 400


def test_uxmaster_400_when_files_empty():
    r = client.post("/api/uxmaster", json={"files": {}, "image": _DATA_URL})
    assert r.status_code == 400


# ── premium gate (honored ONLY for SUPER_ADMIN) ──────────────────────────────

def _override_user(role: str):
    user = SimpleNamespace(id=_uuid.uuid4(), email="u@x.com", name="U", role=role)
    app.dependency_overrides[get_current_user] = lambda: user


def test_uxmaster_premium_ignored_for_non_admin():
    _override_user("user")
    session = _mock_db_session()
    vision_mock = MagicMock(return_value=_VISION_REPLY)
    with (
        patch("api.uxmaster.chat_vision", vision_mock),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/uxmaster",
            json={"files": _SAMPLE_FILES, "image": _DATA_URL, "premium": True},
        )
    assert r.status_code == 200, r.text
    kwargs = vision_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 8192
    assert kwargs["chain"] is VISION_CHAIN


def test_uxmaster_premium_honored_for_super_admin():
    _override_user("SUPER_ADMIN")
    session = _mock_db_session()
    vision_mock = MagicMock(return_value=_VISION_REPLY)
    with (
        patch("api.uxmaster.chat_vision", vision_mock),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/uxmaster",
            json={"files": _SAMPLE_FILES, "image": _DATA_URL, "premium": True},
        )
    assert r.status_code == 200, r.text
    kwargs = vision_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 20000
