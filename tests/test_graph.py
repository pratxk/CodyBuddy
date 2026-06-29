import asyncio
import json
import pathlib

import pytest

from agent import graph as g
from agent.events import AgentEventEmitter, BUILD_TOPOLOGY
from agent.scaffold import is_sandpack_shaped, parse_multi_file_response
from agent.llm import strip_code_fences
from agent.states import Plan, File, TaskPlan, ImplementationTask


def test_emitter_pushes_graph_init_and_start():
    async def run():
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        em = AgentEventEmitter(loop, q, BUILD_TOPOLOGY)
        em.graph_init()
        em.start_next()
        await asyncio.sleep(0.01)
        first = json.loads(await q.get())
        second = json.loads(await q.get())
        return first, second

    first, second = asyncio.run(run())
    assert first["type"] == "graph_init"
    assert second["type"] == "agent_start"
    assert second["agent_id"] == "planner"


def test_run_build_returns_sandpack_files_no_disk(tmp_path, monkeypatch):
    plan = Plan(name="TicTacToe", description="game", techStack=["React"],
                features=["play"], files=[File(path="/App.js", purpose="root")])
    task_plan = TaskPlan(implementation_steps=[
        ImplementationTask(filepath="/App.js", task_description="render board"),
    ])

    def fake_structured(prompt, schema, **kw):
        return plan if schema is Plan else task_plan

    # single-call coder now returns delimited multi-file format
    def fake_chat(prompt, **kw):
        return "=== FILE: /App.js ===\nexport default function App(){return <h1>Tic</h1>;}\n"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("tic tac toe")
    assert is_sandpack_shaped(result["files"])
    assert "/App.js" in result["files"]
    assert "Tic" in result["files"]["/App.js"]
    # no generated_project dir created
    assert not (pathlib.Path.cwd() / "generated_project").exists()


def test_run_build_premium_uses_higher_budget_and_premium_prompt(monkeypatch):
    plan = Plan(name="SocialDash", description="saas", techStack=["React"],
                features=["dashboard"], files=[File(path="/App.js", purpose="root")])
    task_plan = TaskPlan(implementation_steps=[
        ImplementationTask(filepath="/App.js", task_description="app shell"),
    ])
    captured = {}

    def fake_structured(prompt, schema, **kw):
        return plan if schema is Plan else task_plan

    def fake_chat(prompt, **kw):
        captured["max_tokens"] = kw.get("max_tokens")
        captured["premium_prompt"] = "PREMIUM PRODUCTION-GRADE MODE" in prompt
        return "=== FILE: /App.js ===\nexport default function App(){return <h1>Dash</h1>;}\n"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("social media dashboard", premium=True)
    assert result["files"]["/App.js"]
    assert captured["max_tokens"] == 20000
    assert captured["premium_prompt"] is True


# ── parse_multi_file_response unit tests ─────────────────────────────────────

def test_parse_multi_file_basic():
    raw = (
        "=== FILE: /App.js ===\n"
        "export default function App(){return <h1>Hi</h1>;}\n"
        "=== FILE: /styles.css ===\n"
        "body { margin: 0; }\n"
    )
    files = parse_multi_file_response(raw, strip_code_fences)
    assert set(files.keys()) == {"/App.js", "/styles.css"}
    assert "App" in files["/App.js"]
    assert "margin" in files["/styles.css"]


def test_parse_multi_file_strips_fences():
    raw = (
        "=== FILE: /App.js ===\n"
        "```jsx\n"
        "export default function App(){return <h1>Hi</h1>;}\n"
        "```\n"
    )
    files = parse_multi_file_response(raw, strip_code_fences)
    assert "/App.js" in files
    assert "```" not in files["/App.js"]


def test_parse_multi_file_no_headers_raises():
    with pytest.raises(ValueError, match="No file headers"):
        parse_multi_file_response("just some text with no headers", strip_code_fences)


def test_parse_multi_file_single_file():
    raw = "=== FILE: /index.js ===\nconst x = 1;\n"
    files = parse_multi_file_response(raw, strip_code_fences)
    assert "/index.js" in files
    assert "const x" in files["/index.js"]
