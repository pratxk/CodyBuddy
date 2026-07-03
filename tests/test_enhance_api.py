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


# ── premium gate (mirrors /api/generate: honored ONLY for SUPER_ADMIN) ───────────

import uuid as _uuid
from types import SimpleNamespace

from agent.llm import CODER_CHAIN, CODER_CHAIN_PREMIUM
from auth.dependencies import get_current_user


def _override_user(role: str):
    user = SimpleNamespace(id=_uuid.uuid4(), email="u@x.com", name="U", role=role)
    app.dependency_overrides[get_current_user] = lambda: user


def test_enhance_premium_ignored_for_non_admin():
    _override_user("user")
    session = _mock_db_session()
    chat_mock = MagicMock(return_value=_LLM_WITH_REPLY)
    with (
        patch("api.enhance.chat", chat_mock),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": _SAMPLE_FILES, "instruction": "enhance it", "premium": True},
        )
    assert r.status_code == 200, r.text
    kwargs = chat_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 8192
    assert kwargs["chain"] is CODER_CHAIN


def test_enhance_premium_honored_for_super_admin():
    _override_user("SUPER_ADMIN")
    session = _mock_db_session()
    chat_mock = MagicMock(return_value=_LLM_WITH_REPLY)
    with (
        patch("api.enhance.chat", chat_mock),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": _SAMPLE_FILES, "instruction": "enhance it", "premium": True},
        )
    assert r.status_code == 200, r.text
    kwargs = chat_mock.call_args.kwargs
    assert kwargs["max_tokens"] == 20000
    assert kwargs["chain"] is CODER_CHAIN_PREMIUM


def test_enhance_preserves_premium_scaffold():
    """Refining a premium app (has /ui/index.js) must never drop/clobber the
    baked /ui kit even when the enhance LLM only re-emits a file or two."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES

    premium_files = {
        **PREMIUM_SCAFFOLD_FILES,
        "/App.js": 'import { Sidebar } from "./ui"; export default function App(){return null;}',
        "/data/mock.js": "export const rows = [];\n",
        "/views/Home.js": 'import { Card } from "../ui"; export default () => <Card/>;',
    }
    # LLM returns a reply + only /App.js + a BROKEN /ui/index.js (drops primitives).
    llm_out = (
        "=== REPLY ===\nMade the header bolder.\n"
        "=== FILE: /App.js ===\n"
        'import { Sidebar } from "./ui"; export default function App(){return <main/>;}\n'
        "=== FILE: /ui/index.js ===\n"
        "export const Toast = () => null; // destructive re-emission\n"
    )
    session = _mock_db_session()
    with (
        patch("api.enhance.chat", return_value=llm_out),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": premium_files, "instruction": "make the header bolder"},
        )
    assert r.status_code == 200, r.text
    out = r.json()["files"]
    # Every baked /ui primitive + /lib survives, and the barrel is the FROZEN one.
    for path in PREMIUM_SCAFFOLD_FILES:
        if path.startswith(("/ui/", "/lib/")):
            assert path in out, f"frozen kit file dropped: {path}"
    assert out["/ui/index.js"] == PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    assert "destructive re-emission" not in out["/ui/index.js"]
    # Un-returned generated files preserved; the LLM's /App.js edit applied.
    assert "/data/mock.js" in out and "/views/Home.js" in out
    assert "<main/>" in out["/App.js"]


def test_enhance_non_premium_unaffected():
    """A plain (non-premium) app must NOT get the scaffold overlaid."""
    session = _mock_db_session()
    with (
        patch("api.enhance.chat", return_value=_LLM_WITH_REPLY),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/enhance",
            json={"files": _SAMPLE_FILES, "instruction": "tweak it"},
        )
    assert r.status_code == 200, r.text
    out = r.json()["files"]
    assert "/ui/index.js" not in out  # no scaffold injected into a plain app


def test_enhance_premium_partial_edit_merges_only_changed_files():
    """A premium edit should apply the LLM's PARTIAL output (only the changed
    file) over the current app — not require re-emitting all 22 files."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES
    premium_files = {
        **PREMIUM_SCAFFOLD_FILES,
        "/App.js": 'import { Sidebar } from "./ui"; export default function App(){return null;}',
        "/data/mock.js": "export const rows = [];\n",
        "/views/Pipeline.js": 'import { Card } from "../ui"; export const V = () => <Card>old</Card>;',
        "/views/Other.js": 'export const O = () => null;',
    }
    # LLM returns ONLY the changed view (partial) — NOT the whole app.
    llm_out = (
        "=== REPLY ===\nAdded a create modal to the pipeline.\n"
        "=== FILE: /views/Pipeline.js ===\n"
        'import { Card, Modal, Button } from "../ui"; export const V = () => <Card>NEW MODAL</Card>;\n'
    )
    session = _mock_db_session()
    with (
        patch("api.enhance.chat", return_value=llm_out),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post("/api/enhance",
                        json={"files": premium_files, "instruction": "add a create modal"})
    assert r.status_code == 200, r.text
    out = r.json()["files"]
    # The changed view is updated…
    assert "NEW MODAL" in out["/views/Pipeline.js"]
    # …and everything the LLM DIDN'T emit is preserved (untouched view, mock, /ui kit).
    assert out["/views/Other.js"] == premium_files["/views/Other.js"]
    assert out["/data/mock.js"] == premium_files["/data/mock.js"]
    assert out["/ui/index.js"] == PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
