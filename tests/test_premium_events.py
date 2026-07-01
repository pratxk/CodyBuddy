"""Phase 4 — dynamic per-view SSE topology tests.

Tests:
- build_premium_topology builds correct node list from a PremiumPlan with 2 views
- graph_update event is emitted with the topology payload
- per-view start_agent/end_agent fire for each view:<id>
- coder_chunk still fires (regression)
- standard BUILD_TOPOLOGY + index-cursor flow is unchanged (regression)
"""
import asyncio
import json
import pytest

from agent.events import AgentEventEmitter, BUILD_TOPOLOGY, build_premium_topology
from agent.states import (
    PremiumPlan,
    PremiumView,
    PremiumArchitecture,
    PremiumViewSpec,
)
from agent import graph as g


# ── helpers / fixtures ────────────────────────────────────────────────────────

def _make_plan(n_views: int = 2) -> PremiumPlan:
    views = [
        PremiumView(
            id=f"view-{i}",
            label=f"View {i}",
            icon=f"Icon{i}",
            purpose=f"purpose {i}",
            kpis=["kpi"],
            table_columns=["col"],
            actions=["act"],
        )
        for i in range(1, n_views + 1)
    ]
    return PremiumPlan(
        name="TestDash",
        palette={"--primary": "#F97316"},
        entities=[],
        views=views,
        mock_data_spec="test story",
    )


def _make_arch(n_views: int = 2) -> PremiumArchitecture:
    specs = [
        PremiumViewSpec(
            view_id=f"view-{i}",
            filepath=f"/views/View{i}.js",
            task_description="compose",
            primitives=["KPIStat", "DataTable"],
            data_keys=[f"rows{i}"],
        )
        for i in range(1, n_views + 1)
    ]
    return PremiumArchitecture(view_specs=specs, mock_schema="rows1:[],rows2:[]")


def _sync_queue(loop: asyncio.AbstractEventLoop) -> list[dict]:
    """Drain all items from the loop's queue synchronously (for test inspection)."""
    q: asyncio.Queue = loop._test_queue  # type: ignore[attr-defined]
    items = []
    while not q.empty():
        raw = q.get_nowait()
        items.append(json.loads(raw))
    return items


def _make_emitter(topology: dict | None = None) -> tuple["AgentEventEmitter", asyncio.AbstractEventLoop, list[dict]]:
    """Create an emitter backed by an in-process event loop; returns (emitter, loop, log_list).
    log_list is filled lazily — call drain_log() to flush pending items."""
    loop = asyncio.new_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    loop._test_queue = queue  # type: ignore[attr-defined]
    topo = topology if topology is not None else BUILD_TOPOLOGY
    emitter = AgentEventEmitter(loop, queue, topo)
    return emitter, loop, queue


def _drain(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> list[dict]:
    """Run all pending coroutines and drain the queue."""
    loop.run_until_complete(asyncio.sleep(0))
    items = []
    while not queue.empty():
        raw = queue.get_nowait()
        items.append(json.loads(raw))
    return items


# ── Unit: build_premium_topology ─────────────────────────────────────────────

def test_build_premium_topology_node_ids():
    plan = _make_plan(2)
    topo = build_premium_topology(plan)
    node_ids = [n["id"] for n in topo["nodes"]]
    assert node_ids == ["planner", "architect", "shell", "view:view-1", "view:view-2", "assemble"]


def test_build_premium_topology_labels_from_views():
    plan = _make_plan(2)
    topo = build_premium_topology(plan)
    view_nodes = [n for n in topo["nodes"] if n["id"].startswith("view:")]
    assert view_nodes[0]["label"] == "View 1"
    assert view_nodes[0]["icon"] == "Icon1"
    assert view_nodes[1]["label"] == "View 2"
    assert view_nodes[1]["icon"] == "Icon2"


def test_build_premium_topology_edges_are_linear():
    plan = _make_plan(2)
    topo = build_premium_topology(plan)
    nodes = topo["nodes"]
    edges = topo["edges"]
    assert len(edges) == len(nodes) - 1
    for i, edge in enumerate(edges):
        assert edge["from"] == nodes[i]["id"]
        assert edge["to"] == nodes[i + 1]["id"]


def test_build_premium_topology_sublabels_from_views():
    plan = _make_plan(2)
    topo = build_premium_topology(plan)
    view_nodes = [n for n in topo["nodes"] if n["id"].startswith("view:")]
    assert view_nodes[0]["sublabel"] == "purpose 1"
    assert view_nodes[1]["sublabel"] == "purpose 2"


# ── Unit: graph_update event ──────────────────────────────────────────────────

def test_graph_update_emits_correct_event():
    emitter, loop, queue = _make_emitter()
    plan = _make_plan(2)
    new_topo = build_premium_topology(plan)
    emitter.graph_update(new_topo)
    events = _drain(loop, queue)
    loop.close()

    assert len(events) == 1
    ev = events[0]
    assert ev["type"] == "graph_update"
    assert ev["topology"] == new_topo


def test_graph_update_replaces_internal_topology():
    emitter, loop, queue = _make_emitter()
    plan = _make_plan(2)
    new_topo = build_premium_topology(plan)
    emitter.graph_update(new_topo)
    _drain(loop, queue)
    loop.close()
    # The emitter's internal _topology and _nodes must be updated
    assert emitter._topology is new_topo
    assert len(emitter._nodes) == len(new_topo["nodes"])


# ── Integration: per-view start_agent / end_agent + graph_update ─────────────

class _RecordingEmitter:
    """Lightweight fake that records method calls without asyncio."""
    def __init__(self):
        self.calls: list[tuple] = []
        self.chunks: list[str] = []

    def graph_init(self):
        self.calls.append(("graph_init",))

    def graph_update(self, topology):
        self.calls.append(("graph_update", topology))

    def start_agent(self, agent_id):
        self.calls.append(("start_agent", agent_id))

    def end_agent(self, agent_id, **kw):
        self.calls.append(("end_agent", agent_id))

    def start_next(self):
        self.calls.append(("start_next",))

    def end_current(self, **kw):
        self.calls.append(("end_current",))

    def chunk(self, text):
        self.chunks.append(text)

    def call_types(self) -> list[str]:
        return [c[0] for c in self.calls]

    def agent_ids_for(self, call_type: str) -> list[str]:
        return [c[1] for c in self.calls if c[0] == call_type]


_SHELL_RAW = (
    "=== FILE: /data/mock.js ===\n"
    "export const rows1 = []; export const rows2 = [];\n"
    "=== FILE: /App.js ===\n"
    "import { Sidebar, Topbar, ToastHost } from \"./ui\";\n"
    "export default function App(){ return <div className=\"app-shell\" />; }\n"
)

_VIEW_RAW_TMPL = (
    "=== FILE: {path} ===\n"
    "import {{ KPIStat, DataTable }} from \"../ui\";\n"
    "export default function View(){{ return <KPIStat label=\"x\" value={{1}} />; }}\n"
)


def _install_fakes(monkeypatch, plan, architecture):
    def fake_structured(prompt, schema, **kw):
        if schema is PremiumPlan:
            return plan
        if schema is PremiumArchitecture:
            return architecture
        raise AssertionError(f"unexpected schema {schema}")

    def fake_stream(prompt, *, on_delta=None, **kw):
        if "PREMIUM SHELL CODER" in prompt:
            raw = _SHELL_RAW
        else:
            import re
            m = re.search(r'/views/(\w+\.js)', prompt)
            fname = m.group(1) if m else "View.js"
            raw = _VIEW_RAW_TMPL.format(path=f"/views/{fname}")
        if on_delta:
            on_delta(raw)
        return raw

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat_stream", fake_stream)


def test_premium_run_emits_graph_update_after_planner(monkeypatch):
    plan = _make_plan(2)
    arch = _make_arch(2)
    _install_fakes(monkeypatch, plan, arch)
    em = _RecordingEmitter()
    g.run_build("build a dash", emitter=em, premium=True, framework="react")

    assert "graph_update" in em.call_types()
    # graph_update must carry the full per-view topology
    topo_calls = [c for c in em.calls if c[0] == "graph_update"]
    assert len(topo_calls) == 1
    topo = topo_calls[0][1]
    node_ids = [n["id"] for n in topo["nodes"]]
    assert "view:view-1" in node_ids
    assert "view:view-2" in node_ids
    assert "assemble" in node_ids


def test_premium_run_emits_per_view_start_end(monkeypatch):
    plan = _make_plan(2)
    arch = _make_arch(2)
    _install_fakes(monkeypatch, plan, arch)
    em = _RecordingEmitter()
    g.run_build("build a dash", emitter=em, premium=True, framework="react")

    starts = em.agent_ids_for("start_agent")
    ends = em.agent_ids_for("end_agent")
    assert "view:view-1" in starts
    assert "view:view-2" in starts
    assert "view:view-1" in ends
    assert "view:view-2" in ends


def test_premium_run_emits_lifecycle_for_all_stages(monkeypatch):
    plan = _make_plan(2)
    arch = _make_arch(2)
    _install_fakes(monkeypatch, plan, arch)
    em = _RecordingEmitter()
    g.run_build("build a dash", emitter=em, premium=True, framework="react")

    starts = em.agent_ids_for("start_agent")
    ends = em.agent_ids_for("end_agent")
    for stage in ("planner", "architect", "shell", "view:view-1", "view:view-2", "assemble"):
        assert stage in starts or stage in ends, f"stage '{stage}' missing from emitter events"


def test_premium_run_still_emits_coder_chunks(monkeypatch):
    plan = _make_plan(2)
    arch = _make_arch(2)
    _install_fakes(monkeypatch, plan, arch)
    em = _RecordingEmitter()
    g.run_build("build a dash", emitter=em, premium=True, framework="react")
    # shell + 2 views = at least 3 delta calls
    assert len(em.chunks) >= 3


# ── Regression: standard BUILD_TOPOLOGY + index cursor unchanged ──────────────

def test_standard_build_topology_unchanged():
    """BUILD_TOPOLOGY must stay as the 3-node (planner/architect/coder) static dict."""
    assert len(BUILD_TOPOLOGY["nodes"]) == 3
    ids = [n["id"] for n in BUILD_TOPOLOGY["nodes"]]
    assert ids == ["planner", "architect", "coder"]
    assert len(BUILD_TOPOLOGY["edges"]) == 2


def test_standard_emitter_index_cursor_unchanged(monkeypatch):
    """Standard path uses start_next/end_current (index cursor) — must not be broken."""
    from agent.states import Plan, File, TaskPlan, ImplementationTask

    def fake_structured(prompt, schema, **kw):
        if schema is Plan:
            return Plan(name="A", description="d", techStack=["React"],
                        features=["f"], files=[File(path="/App.js", purpose="p")])
        return TaskPlan(implementation_steps=[
            ImplementationTask(filepath="/App.js", task_description="render")])

    def fake_stream(prompt, **kw):
        return "=== FILE: /App.js ===\nexport default function App(){return <h1/>;}\n"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat_stream", fake_stream)

    em = _RecordingEmitter()
    g.run_build("a plain react app", emitter=em, premium=False, framework="react")

    # Standard path must use start_next / end_current (index-based)
    assert "start_next" in em.call_types()
    assert "end_current" in em.call_types()
    # Standard path must NOT emit graph_update
    assert "graph_update" not in em.call_types()
