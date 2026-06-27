import asyncio
import json
from agent.events import AgentEventEmitter, BUILD_TOPOLOGY


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


from unittest.mock import patch
from agent import graph as g
from agent.states import Plan, File, TaskPlan, ImplementationTask
from agent.scaffold import is_sandpack_shaped


def test_run_build_returns_sandpack_files_no_disk(tmp_path, monkeypatch):
    plan = Plan(name="TicTacToe", description="game", techStack=["React"],
                features=["play"], files=[File(path="/App.js", purpose="root")])
    task_plan = TaskPlan(implementation_steps=[
        ImplementationTask(filepath="/App.js", task_description="render board"),
    ])

    def fake_structured(prompt, schema, **kw):
        return plan if schema is Plan else task_plan

    def fake_chat(prompt, **kw):
        return "export default function App(){return <h1>Tic</h1>;}"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("tic tac toe")
    assert is_sandpack_shaped(result["files"])
    assert "/App.js" in result["files"]
    assert "Tic" in result["files"]["/App.js"]
    # no generated_project dir created
    import pathlib
    assert not (pathlib.Path.cwd() / "generated_project").exists()
