import asyncio
import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Build topology ────────────────────────────────────────────────────────────

BUILD_TOPOLOGY: dict = {
    "nodes": [
        {"id": "planner",   "label": "Planner",   "sublabel": "Designs the build plan", "icon": "ClipboardList"},
        {"id": "architect", "label": "Architect", "sublabel": "Breaks into file tasks",  "icon": "Network"},
        {"id": "coder",     "label": "Coder",     "sublabel": "Writes all files",        "icon": "Code"},
    ],
    "edges": [
        {"from": "planner", "to": "architect"},
        {"from": "architect", "to": "coder"},
    ],
}


class AgentEventEmitter:
    """
    Thread-safe per-agent lifecycle emitter.
    Safe to call from a ThreadPoolExecutor worker — all pushes go through
    asyncio.run_coroutine_threadsafe so no event-loop wiring is needed at the call site.

    Usage:
        emitter = AgentEventEmitter(loop, queue, topology)
        emitter.graph_init()   # send topology skeleton to FE
        emitter.start_next()   # start first agent

        # in task_callback (fires after each task):
        emitter.end_current(ok=True)
        emitter.start_next()   # no-op after the last agent
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
        topology: dict,
    ) -> None:
        self._loop = loop
        self._queue = queue
        self._topology = topology
        self._nodes: list[dict] = topology["nodes"]
        self._current_idx: int = -1
        self._start_times: dict[str, float] = {}

    # ── private ───────────────────────────────────────────────────────────────

    def _push(self, **payload) -> None:
        asyncio.run_coroutine_threadsafe(
            self._queue.put(json.dumps(payload)), self._loop
        )

    # ── public API ────────────────────────────────────────────────────────────

    def graph_init(self) -> None:
        """Emit the full topology so the FE can render the graph skeleton immediately."""
        self._push(type="graph_init", topology=self._topology)

    def start_next(self) -> None:
        """Advance to the next agent and emit agent_start. No-op past the last agent."""
        self._current_idx += 1
        if self._current_idx >= len(self._nodes):
            return
        node = self._nodes[self._current_idx]
        self._start_times[node["id"]] = time.monotonic()
        self._push(type="agent_start", agent_id=node["id"], label=node["label"])

    def end_current(self, ok: bool = True, error: Optional[str] = None) -> None:
        """Emit agent_end for the currently running agent."""
        if self._current_idx < 0 or self._current_idx >= len(self._nodes):
            return
        node = self._nodes[self._current_idx]
        start = self._start_times.get(node["id"], time.monotonic())
        duration_ms = int((time.monotonic() - start) * 1000)
        self._push(
            type="agent_end",
            agent_id=node["id"],
            ok=ok,
            error=error,
            duration_ms=duration_ms,
        )

    def start_agent(self, agent_id: str) -> None:
        """Start a specific agent by ID (used for conditional/branching graphs)."""
        node = next((n for n in self._nodes if n["id"] == agent_id), None)
        if node is None:
            return
        self._start_times[agent_id] = time.monotonic()
        self._push(type="agent_start", agent_id=agent_id, label=node["label"])

    def end_agent(self, agent_id: str, ok: bool = True, error: Optional[str] = None) -> None:
        """End a specific agent by ID (used for conditional/branching graphs)."""
        node = next((n for n in self._nodes if n["id"] == agent_id), None)
        if node is None:
            return
        start = self._start_times.get(agent_id, time.monotonic())
        duration_ms = int((time.monotonic() - start) * 1000)
        self._push(type="agent_end", agent_id=agent_id, ok=ok, error=error, duration_ms=duration_ms)
