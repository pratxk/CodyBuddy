"""
Tests for POST /api/oncall — network/DB-free.
Auth is bypassed via conftest override.
session_id is now optional/ignored; removed tests for blank session_id validation.
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
    row.user_id = uuid.UUID("aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb")

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
            },
        )
    assert r.status_code == 200
    assert "/App.js" in r.json()["files"]


def test_oncall_validation_blank_error():
    r = client.post(
        "/api/oncall",
        json={"files": _SAMPLE_FILES, "error": "   "},
    )
    assert r.status_code == 400
    assert "error" in r.json()["detail"].lower()


def test_oncall_validation_empty_files():
    r = client.post(
        "/api/oncall",
        json={"files": {}, "error": "some error"},
    )
    assert r.status_code == 400
    assert "files" in r.json()["detail"].lower()


def test_oncall_preserves_premium_scaffold():
    """A premium app (has /ui/index.js) must keep its baked kit even when the
    non-premium OnCall LLM only returns a couple of files. The 12 baked /ui/*
    primitives, /lib/format.js and /data/mock.js must survive, and the barrel
    must be the FROZEN baked version (never the LLM's re-emission)."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES

    # A premium-shaped project: baked kit + a generated shell/view/data.
    premium_files = {
        **PREMIUM_SCAFFOLD_FILES,
        "/App.js": 'import { Sidebar } from "./ui"; export default function App(){return null;}',
        "/data/mock.js": "export const rows = [];\n",
        "/views/Home.js": 'import { Card } from "../ui"; export default () => <Card/>;',
    }

    # The LLM autofix returns ONLY /App.js AND a broken /ui/index.js (drops the
    # 11 primitives) — exactly the destructive regeneration we must neutralise.
    llm_out = (
        "=== FILE: /App.js ===\n"
        'import { Sidebar } from "./ui"; export default function App(){return <div/>;}\n'
        "=== FILE: /ui/index.js ===\n"
        'export const Toast = () => null; // LLM re-emission that drops the barrel\n'
    )

    session = _mock_db_session()
    with (
        patch("api.oncall.chat", return_value=llm_out),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/oncall",
            json={"files": premium_files, "error": "some runtime error"},
        )
    assert r.status_code == 200, r.text
    out = r.json()["files"]

    # All 12 baked primitives + lib survive.
    for path in PREMIUM_SCAFFOLD_FILES:
        assert path in out, f"baked scaffold file dropped: {path}"

    # The barrel is the FROZEN baked version, not the LLM's re-emission.
    assert out["/ui/index.js"] == PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    assert "export { default as Card }" in out["/ui/index.js"]
    assert "LLM re-emission" not in out["/ui/index.js"]

    # Generated files the LLM DIDN'T return are preserved from the original.
    assert "/data/mock.js" in out
    assert "/views/Home.js" in out

    # The LLM's actual fix to /App.js is applied.
    assert "<div/>" in out["/App.js"]


def test_oncall_non_premium_unaffected():
    """A standard (non-premium) app has no /ui/index.js — OnCall behaves exactly
    as before (no scaffold overlay), so the LLM output is authoritative."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES

    session = _mock_db_session()
    with (
        patch("api.oncall.chat", return_value=_LLM_RESPONSE),
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post(
            "/api/oncall",
            json={"files": _SAMPLE_FILES, "error": "some error"},
        )
    assert r.status_code == 200
    out = r.json()["files"]
    # No baked primitives leaked into a plain app.
    assert "/ui/Card.js" not in out
    assert "/ui/index.js" not in out or out["/ui/index.js"] != PREMIUM_SCAFFOLD_FILES["/ui/index.js"]


def test_oncall_premium_scoped_touches_only_broken_file():
    """A premium repair must fix ONLY the file the error names — not rewrite the
    app — and preserve the frozen kit (/ui, /styles.css, /lib) + other views."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES
    premium = {
        **PREMIUM_SCAFFOLD_FILES,
        "/App.js": 'import { AppShell } from "./ui"; export default () => <AppShell/>;',
        "/data/mock.js": "export const rows = [];\n",
        "/views/Pipeline.js": 'export const V = () => { const x = [1,2 3]; return null; };',  # syntax error
        "/views/Other.js": 'export const O = () => null;',
    }
    # OnCall returns ONLY the fixed broken file.
    llm_out = (
        "=== FILE: /views/Pipeline.js ===\n"
        'export const V = () => { const x = [1,2,3]; return null; };\n'
    )
    session = _mock_db_session()
    with (
        patch("api.oncall.chat", return_value=llm_out) as chat_mock,
        patch("api.enhance.SessionLocal", return_value=session),
    ):
        r = client.post("/api/oncall", json={
            "files": premium,
            "error": "SyntaxError: /views/Pipeline.js: Unexpected number (1:31)",
        })
    assert r.status_code == 200, r.text
    out = r.json()["files"]
    # Only the broken file was fixed; everything else is byte-identical.
    assert "[1,2,3]" in out["/views/Pipeline.js"]
    assert out["/views/Other.js"] == premium["/views/Other.js"]
    assert out["/App.js"] == premium["/App.js"]
    assert out["/data/mock.js"] == premium["/data/mock.js"]
    assert out["/ui/index.js"] == PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    assert out["/styles.css"] == PREMIUM_SCAFFOLD_FILES["/styles.css"]
    # The prompt sent to the LLM was SCOPED — it did not embed unrelated views.
    sent = chat_mock.call_args.args[0]
    assert "/views/Pipeline.js" in sent
    assert "/views/Other.js" not in sent  # not implicated → not shown
