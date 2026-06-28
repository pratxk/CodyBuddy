"""
Tests for POST /api/intake — network-free (chat_structured is mocked).
Auth is bypassed via conftest override.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.states import IntakeStep
from api.main import app

client = TestClient(app)


def test_intake_vague_prompt_asks_question():
    """A vague prompt should yield ready=false with a question + options."""
    asking = IntakeStep(
        ready=False,
        question="What kind of app do you want to build?",
        options=["A game", "A productivity tool", "A dashboard"],
    )
    with patch("api.intake.chat_structured", return_value=asking):
        r = client.post("/api/intake", json={"prompt": "build me an app"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is False
    assert body["question"]
    assert len(body["options"]) >= 2
    assert body["brief"] is None


def test_intake_specific_prompt_returns_brief():
    """A specific prompt should yield ready=true with a brief."""
    ready = IntakeStep(
        ready=True,
        brief="Build a tic-tac-toe game with a 3x3 board and a running score for X and O.",
    )
    with patch("api.intake.chat_structured", return_value=ready):
        r = client.post("/api/intake", json={"prompt": "a tic-tac-toe game with score"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert "tic-tac-toe" in body["brief"]
    assert body["question"] is None


def test_intake_hard_cap_forces_ready():
    """At history length >= 5 the cap forces ready even if the model keeps asking."""
    asking = IntakeStep(
        ready=False, question="One more thing?", options=["a", "b"]
    )
    history = [{"question": f"q{i}", "answer": f"ans{i}"} for i in range(5)]
    with patch("api.intake.chat_structured", return_value=asking):
        r = client.post(
            "/api/intake",
            json={"prompt": "build me an app", "history": history},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert "build me an app" in body["brief"]
    assert "ans0" in body["brief"]


def test_intake_ready_without_brief_falls_back_to_prompt():
    """ready=true but empty brief should fall back to the prompt text."""
    ready_no_brief = IntakeStep(ready=True, brief="")
    with patch("api.intake.chat_structured", return_value=ready_no_brief):
        r = client.post("/api/intake", json={"prompt": "a kanban board"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ready"] is True
    assert body["brief"] == "a kanban board"


def test_intake_empty_prompt_returns_400():
    r = client.post("/api/intake", json={"prompt": "   "})
    assert r.status_code == 400
    assert "prompt" in r.json()["detail"].lower()
