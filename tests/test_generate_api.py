import json
import uuid
import asyncio

from fastapi.testclient import TestClient

from api.main import app
import api.generate as gen_module

client = TestClient(app)


def _fake_run_build(brief, emitter=None, premium=False, framework="react"):
    """Fast fake run_build: no network calls, returns deterministic output."""
    plan = type("Plan", (), {"name": "TestApp"})()
    return {"plan": plan, "files": {"/App.js": "console.log('hello');"}, "framework": framework}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_generate_start_returns_job_id():
    from unittest.mock import patch
    with patch("api.generate.run_build", _fake_run_build):
        r = client.post("/api/generate/start", json={"brief": "tic tac toe"})
        assert r.status_code == 200
        assert "job_id" in r.json()


def test_generate_events_streams_result_and_done():
    """SSE stream returns a result event then a done event (network-free, deterministic)."""
    job_id = str(uuid.uuid4())

    # Pre-populate the queue directly — no background thread needed, no sleep
    queue: asyncio.Queue = asyncio.Queue()
    result_payload = json.dumps({"type": "result", "name": "TestApp", "files": {"/App.js": "console.log('hello');"}})
    queue.put_nowait(result_payload)
    queue.put_nowait(gen_module._DONE)
    gen_module._job_queues[job_id] = queue

    sse_resp = client.get(f"/api/generate/events/{job_id}")
    assert sse_resp.status_code == 200

    raw = sse_resp.text
    events = [
        json.loads(line[len("data: "):])
        for line in raw.splitlines()
        if line.startswith("data: ")
    ]

    assert len(events) >= 2, f"Expected >=2 events, got: {events}"

    result_events = [e for e in events if e.get("type") == "result"]
    assert result_events, f"No result event found in: {events}"
    result = result_events[0]
    assert result["name"] == "TestApp"
    assert "/App.js" in result["files"]

    done_events = [e for e in events if e.get("type") == "done"]
    assert done_events, f"No done event found in: {events}"


def test_generate_events_unknown_job_returns_404():
    r = client.get("/api/generate/events/nonexistent-job-id")
    assert r.status_code == 404


# ── premium gate (server-side: honored ONLY for SUPER_ADMIN) ─────────────────────

def test_resolve_premium_ignored_for_non_admin():
    from types import SimpleNamespace
    from api.generate import _resolve_premium
    assert _resolve_premium(True, SimpleNamespace(role="user")) is False


def test_resolve_premium_honored_for_super_admin():
    from types import SimpleNamespace
    from api.generate import _resolve_premium
    assert _resolve_premium(True, SimpleNamespace(role="SUPER_ADMIN")) is True


def test_resolve_premium_false_stays_false_for_admin():
    from types import SimpleNamespace
    from api.generate import _resolve_premium
    assert _resolve_premium(False, SimpleNamespace(role="SUPER_ADMIN")) is False


def test_resolve_premium_missing_role_is_false():
    from types import SimpleNamespace
    from api.generate import _resolve_premium
    assert _resolve_premium(True, SimpleNamespace()) is False


def test_generate_start_accepts_premium_flag_non_admin():
    """Non-admin (FAKE_USER role='user') may send premium=True; endpoint still returns a job."""
    from unittest.mock import patch
    with patch("api.generate.run_build", _fake_run_build):
        r = client.post("/api/generate/start", json={"brief": "social dashboard", "premium": True})
        assert r.status_code == 200
        assert "job_id" in r.json()


# ── framework: request validation + threading + result event ─────────────────


def test_generate_request_validates_framework():
    from api.generate import GenerateRequest
    assert GenerateRequest(brief="x", framework="nextjs").framework == "nextjs"
    assert GenerateRequest(brief="x", framework="svelte").framework == "react"  # invalid → default
    assert GenerateRequest(brief="x").framework == "react"                       # absent → default


def test_generate_threads_framework_into_result(monkeypatch):
    """framework flows start → run_build → result SSE event."""
    captured = {}

    def fake_run_build(brief, emitter=None, premium=False, framework="react"):
        captured["framework"] = framework
        plan = type("Plan", (), {"name": "StaticApp"})()
        return {"plan": plan, "files": {"/index.html": "<h1>hi</h1>"}, "framework": framework}

    monkeypatch.setattr("api.generate.run_build", fake_run_build)
    monkeypatch.setattr("api.generate._persist_project", lambda *a, **k: None)

    start = client.post("/api/generate/start", json={"brief": "a vanilla site", "framework": "static"})
    assert start.status_code == 200
    job_id = start.json()["job_id"]

    sse = client.get(f"/api/generate/events/{job_id}")
    events = [json.loads(l[len("data: "):]) for l in sse.text.splitlines() if l.startswith("data: ")]
    result = next(e for e in events if e.get("type") == "result")
    assert result["framework"] == "static"
    assert captured["framework"] == "static"


# ── Phase 5: premium threads end-to-end into run_build (SUPER_ADMIN only) ─────
# The multi-pass premium subgraph is selected inside run_build when premium=True
# AND framework=="react"; here we prove the API threads the SERVER-RESOLVED
# premium flag (SUPER_ADMIN gate) all the way into run_build.

from types import SimpleNamespace as _SNS

from auth.dependencies import get_current_user as _gcu


def _override_role(role):
    from api.main import app as _app
    user = _SNS(id=uuid.uuid4(), email="u@x.com", name="U", role=role)
    _app.dependency_overrides[_gcu] = lambda: user


def _run_and_capture_premium(monkeypatch, requested_premium, framework="react"):
    captured = {}

    def fake_run_build(brief, emitter=None, premium=False, framework="react"):
        captured["premium"] = premium
        captured["framework"] = framework
        plan = type("Plan", (), {"name": "PremiumApp"})()
        return {"plan": plan, "files": {"/App.js": "x", "/ui/index.js": "y"}, "framework": framework}

    monkeypatch.setattr("api.generate.run_build", fake_run_build)
    monkeypatch.setattr("api.generate._persist_project", lambda *a, **k: None)

    body = {"brief": "a loan origination dashboard", "premium": requested_premium, "framework": framework}
    start = client.post("/api/generate/start", json=body)
    assert start.status_code == 200, start.text
    job_id = start.json()["job_id"]
    # Drain the SSE so the background job actually runs to completion.
    client.get(f"/api/generate/events/{job_id}")
    return captured


def test_premium_threads_into_run_build_for_super_admin(monkeypatch):
    _override_role("SUPER_ADMIN")
    try:
        captured = _run_and_capture_premium(monkeypatch, requested_premium=True, framework="react")
        assert captured["premium"] is True
        assert captured["framework"] == "react"
    finally:
        from api.main import app as _app
        _app.dependency_overrides.pop(_gcu, None)


def test_premium_downgraded_to_standard_for_non_admin(monkeypatch):
    _override_role("user")
    try:
        captured = _run_and_capture_premium(monkeypatch, requested_premium=True, framework="react")
        # Non-admin asking for premium → run_build receives premium=False (standard path).
        assert captured["premium"] is False
    finally:
        from api.main import app as _app
        _app.dependency_overrides.pop(_gcu, None)
