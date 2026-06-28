import json
import uuid
import asyncio

from fastapi.testclient import TestClient

from api.main import app
import api.generate as gen_module

client = TestClient(app)


def _fake_run_build(brief, emitter=None):
    """Fast fake run_build: no network calls, returns deterministic output."""
    plan = type("Plan", (), {"name": "TestApp"})()
    return {"plan": plan, "files": {"/App.js": "console.log('hello');"}}


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
