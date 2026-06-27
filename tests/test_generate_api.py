from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_generate_start_returns_job_id():
    r = client.post("/api/generate/start", json={"brief": "tic tac toe"})
    assert r.status_code == 200
    assert "job_id" in r.json()
