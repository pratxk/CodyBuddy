import json
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app

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
    with patch("api.generate.run_build", _fake_run_build):
        r = client.post("/api/generate/start", json={"brief": "tic tac toe"})
        assert r.status_code == 200
        assert "job_id" in r.json()


def test_generate_events_streams_result_and_done():
    """SSE stream returns a result event then a done event (network-free)."""
    with patch("api.generate.run_build", _fake_run_build):
        r = client.post("/api/generate/start", json={"brief": "tic tac toe"})
        assert r.status_code == 200
        job_id = r.json()["job_id"]

        # Give the background thread a moment to enqueue events.
        time.sleep(0.2)

        sse_resp = client.get(f"/api/generate/events/{job_id}")
        assert sse_resp.status_code == 200

        raw = sse_resp.text
        # Parse SSE lines: lines that start with "data: "
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
