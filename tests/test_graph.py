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
