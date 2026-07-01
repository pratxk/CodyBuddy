"""Phase 3 — premium multi-pass subgraph tests (mock the LLM, no network)."""
import pytest

from agent import graph as g
from agent.states import (PremiumPlan, PremiumView, PremiumViewSpec,
                          PremiumArchitecture)


# ── fixtures / fakes ─────────────────────────────────────────────────────────

def _plan(n_views=2):
    views = [
        PremiumView(id=f"step{i}", label=f"Step {i}", icon="Users",
                    purpose="do things", kpis=["A", "B"],
                    table_columns=["name", "status"], actions=["approve"])
        for i in range(1, n_views + 1)
    ]
    return PremiumPlan(name="LoanFlow", palette={"--primary": "#F97316"},
                       entities=[], views=views, mock_data_spec="one coherent story")


def _architecture(n_views=2):
    specs = [
        PremiumViewSpec(view_id=f"step{i}", filepath=f"/views/Step{i}.js",
                        task_description="compose KPIs + table",
                        primitives=["KPIStat", "DataTable", "Badge", "Button"],
                        data_keys=[f"rows{i}"])
        for i in range(1, n_views + 1)
    ]
    return PremiumArchitecture(view_specs=specs, mock_schema="rows1: [...], rows2: [...]")


class _FakeEmitter:
    def __init__(self):
        self.chunks = []
        self.events = []
        self.topologies = []
        self.agent_starts = []
        self.agent_ends = []
    def graph_init(self):
        self.events.append("graph_init")
    def graph_update(self, topology):
        self.events.append("graph_update")
        self.topologies.append(topology)
    def start_next(self):
        self.events.append("start_next")
    def end_current(self, **kw):
        self.events.append("end_current")
    def start_agent(self, agent_id):
        self.events.append(f"start_agent:{agent_id}")
        self.agent_starts.append(agent_id)
    def end_agent(self, agent_id, **kw):
        self.events.append(f"end_agent:{agent_id}")
        self.agent_ends.append(agent_id)
    def chunk(self, text):
        self.chunks.append(text)


def _install_fakes(monkeypatch, plan, architecture, shell_raw, view_raw_for, *,
                   structured_calls=None, stream_calls=None):
    """Wire fake chat_structured + chat_stream. view_raw_for(spec_json)->str."""
    structured_calls = structured_calls if structured_calls is not None else []
    stream_calls = stream_calls if stream_calls is not None else []

    def fake_structured(prompt, schema, **kw):
        structured_calls.append(schema.__name__)
        if schema is PremiumPlan:
            return plan
        if schema is PremiumArchitecture:
            return architecture
        raise AssertionError(f"unexpected schema {schema}")

    def fake_stream(prompt, *, on_delta=None, **kw):
        stream_calls.append(prompt)
        if "PREMIUM SHELL CODER" in prompt:
            raw = shell_raw
        else:
            raw = view_raw_for(prompt)
        if on_delta:
            on_delta(raw)
        return raw

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat_stream", fake_stream)
    return structured_calls, stream_calls


def _default_view_raw(prompt):
    # Each view spec names its filepath (/views/StepN.js) in the JSON prompt.
    import re
    m = re.search(r'/views/(\w+\.js)', prompt)
    fname = m.group(1) if m else "View.js"
    return (f"=== FILE: /views/{fname} ===\n"
            "import { KPIStat, DataTable, Badge, Button } from \"../ui\";\n"
            "import { rows1 } from \"../data/mock\";\n"
            "export default function View(){ return <KPIStat label=\"x\" value={1} />; }\n")


_SHELL_RAW = (
    "=== FILE: /data/mock.js ===\n"
    "export const rows1 = []; export const rows2 = [];\n"
    "=== FILE: /App.js ===\n"
    "import \"./styles.css\";\n"
    "import { Sidebar, Topbar, ToastHost } from \"./ui\";\n"
    "export default function App(){ return <div className=\"app-shell\" />; }\n"
)


# ── tests ────────────────────────────────────────────────────────────────────

def test_run_build_premium_react_composes_scaffold_shell_and_views(monkeypatch):
    plan, arch = _plan(2), _architecture(2)
    structured, stream = _install_fakes(monkeypatch, plan, arch, _SHELL_RAW,
                                        _default_view_raw)

    result = g.run_build("build a loan tool", premium=True, framework="react")
    files = result["files"]

    # baked scaffold present
    assert "/ui/index.js" in files
    assert "/styles.css" in files
    # shell present
    assert "/App.js" in files
    assert "/data/mock.js" in files
    # both views present
    assert "/views/Step1.js" in files
    assert "/views/Step2.js" in files
    # plan passthrough + framework
    assert result["plan"] is plan
    assert result["framework"] == "react"
    # planner -> architect were both called
    assert structured == ["PremiumPlan", "PremiumArchitecture"]
    # dependencies backfilled (lucide-react/recharts imported by scaffold primitives)
    import json
    deps = json.loads(files["/package.json"])["dependencies"]
    assert "lucide-react" in deps and "recharts" in deps


def test_assemble_baked_scaffold_wins_over_llm_reemission(monkeypatch):
    """Regression: if the shell/view coder re-emits a scaffold file (e.g. its own
    /ui/index.js that drops the barrel, or a partial /styles.css), the FROZEN
    baked version must win — otherwise the barrel imports vanish and the preview
    fails with "Could not find module './ui'". Scaffold is overlaid LAST."""
    from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES

    plan, arch = _plan(1), _architecture(1)

    # A hostile shell that RE-EMITS /ui/index.js and /styles.css (which it must not).
    hostile_shell = (
        "=== FILE: /data/mock.js ===\n"
        "export const rows1 = [];\n"
        "=== FILE: /App.js ===\n"
        'import { Sidebar } from "./ui"; export default function App(){ return <div/>; }\n'
        "=== FILE: /ui/index.js ===\n"
        "export const Toast = () => null; // LLM re-emission that drops the barrel\n"
        "=== FILE: /styles.css ===\n"
        "body{}\n"
    )
    _install_fakes(monkeypatch, plan, arch, hostile_shell, _default_view_raw)

    files = g.run_build("x", premium=True, framework="react")["files"]

    # The baked barrel + styles win, not the LLM re-emission.
    assert files["/ui/index.js"] == PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    assert "export { default as Card }" in files["/ui/index.js"]
    assert "LLM re-emission" not in files["/ui/index.js"]
    assert files["/styles.css"] == PREMIUM_SCAFFOLD_FILES["/styles.css"]
    # All 12 baked primitives are present (nothing dropped).
    for path in PREMIUM_SCAFFOLD_FILES:
        assert path in files, f"baked scaffold dropped: {path}"


def test_two_views_run_through_executor(monkeypatch):
    plan, arch = _plan(2), _architecture(2)
    structured, stream = _install_fakes(monkeypatch, plan, arch, _SHELL_RAW,
                                        _default_view_raw)

    result = g.run_build("x", premium=True, framework="react")
    view_calls = [p for p in stream if "PREMIUM VIEW CODER" in p]
    shell_calls = [p for p in stream if "PREMIUM SHELL CODER" in p]
    assert len(view_calls) == 2      # one chat_stream per view
    assert len(shell_calls) == 1
    assert "/views/Step1.js" in result["files"]
    assert "/views/Step2.js" in result["files"]


def test_coherence_validator_triggers_repair_on_orphan_import(monkeypatch):
    plan, arch = _plan(1), _architecture(1)

    def bad_view(prompt):
        # Orphan import: pulls a nonexistent primitive `Sparkline` from ../ui.
        return ("=== FILE: /views/Step1.js ===\n"
                "import { KPIStat, Sparkline } from \"../ui\";\n"
                "export default function View(){ return <KPIStat label=\"x\" value={1} />; }\n")

    _install_fakes(monkeypatch, plan, arch, _SHELL_RAW, bad_view)

    repair_calls = []
    def fake_chat(prompt, **kw):
        repair_calls.append(prompt)
        return ("=== FILE: /views/Step1.js ===\n"
                "import { KPIStat } from \"../ui\";\n"
                "export default function View(){ return <KPIStat label=\"x\" value={1} />; }\n")

    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("x", premium=True, framework="react")
    # repair ran exactly once and healed the orphan import
    assert len(repair_calls) == 1
    assert "Sparkline" not in result["files"]["/views/Step1.js"]
    assert "/views/Step1.js" in result["files"]


def test_repair_failure_keeps_best_version_no_crash(monkeypatch):
    plan, arch = _plan(1), _architecture(1)

    def bad_view(prompt):
        return ("=== FILE: /views/Step1.js ===\n"
                "import { KPIStat, Sparkline } from \"../ui\";\n"
                "export default function View(){ return null; }\n")

    _install_fakes(monkeypatch, plan, arch, _SHELL_RAW, bad_view)

    # repair still returns a broken view -> must not crash, keeps a version.
    def fake_chat(prompt, **kw):
        return ("=== FILE: /views/Step1.js ===\n"
                "import { KPIStat, Sparkline } from \"../ui\";\n"
                "export default function View(){ return null; }\n")

    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("x", premium=True, framework="react")
    assert "/views/Step1.js" in result["files"]  # build did not crash


def test_premium_planner_caps_views_at_six(monkeypatch):
    plan, arch = _plan(8), _architecture(8)
    _install_fakes(monkeypatch, plan, arch, _SHELL_RAW, _default_view_raw)
    result = g.run_build("x", premium=True, framework="react")
    view_files = [k for k in result["files"] if k.startswith("/views/")]
    assert len(view_files) <= 6


def test_emitter_streams_coder_chunks(monkeypatch):
    plan, arch = _plan(2), _architecture(2)
    _install_fakes(monkeypatch, plan, arch, _SHELL_RAW, _default_view_raw)
    em = _FakeEmitter()
    g.run_build("x", emitter=em, premium=True, framework="react")
    # shell + 2 views => at least 3 coder_chunk deltas
    assert len(em.chunks) >= 3
    assert "graph_init" in em.events


# ── regression: non-react premium and standard builds use the OLD graph ──────

def test_regression_premium_nextjs_uses_standard_graph(monkeypatch):
    from agent.states import Plan, File, TaskPlan, ImplementationTask
    premium_called = {"planner": 0}

    def fake_structured(prompt, schema, **kw):
        if schema is PremiumPlan:
            premium_called["planner"] += 1
        if schema is Plan:
            return Plan(name="N", description="d", techStack=["Next.js"],
                        features=["f"], files=[File(path="/app/page.tsx", purpose="p")])
        return TaskPlan(implementation_steps=[
            ImplementationTask(filepath="/app/page.tsx", task_description="page")])

    def fake_stream(prompt, **kw):
        return "=== FILE: /app/page.tsx ===\nexport default function Page(){return <h1/>;}\n"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat_stream", fake_stream)

    result = g.run_build("a next app", premium=True, framework="nextjs")
    assert result["framework"] == "nextjs"
    assert premium_called["planner"] == 0   # premium multi-pass NOT invoked


def test_regression_standard_react_uses_standard_graph(monkeypatch):
    from agent.states import Plan, File, TaskPlan, ImplementationTask
    premium_called = {"planner": 0}

    def fake_structured(prompt, schema, **kw):
        if schema is PremiumPlan:
            premium_called["planner"] += 1
        if schema is Plan:
            return Plan(name="R", description="d", techStack=["React"],
                        features=["f"], files=[File(path="/App.js", purpose="p")])
        return TaskPlan(implementation_steps=[
            ImplementationTask(filepath="/App.js", task_description="render")])

    def fake_stream(prompt, **kw):
        return "=== FILE: /App.js ===\nexport default function App(){return <h1/>;}\n"

    monkeypatch.setattr(g, "chat_structured", fake_structured)
    monkeypatch.setattr(g, "chat_stream", fake_stream)

    result = g.run_build("a plain react app", premium=False, framework="react")
    assert premium_called["planner"] == 0   # standard path, no premium nodes
    assert "/App.js" in result["files"]


# ── Phase 4 minors ───────────────────────────────────────────────────────────

def test_shell_orphan_import_triggers_repair(monkeypatch):
    """Minor #1 — if /App.js imports a /views/<X>.js that the view worker returned {} for,
    _validate_and_repair detects the orphan shell import and runs exactly one targeted repair;
    the build returns without crashing and the view file is present."""
    plan, arch = _plan(1), _architecture(1)

    # Shell references Step1.js, but the view worker will return {} for it.
    shell_with_orphan_import = (
        "=== FILE: /data/mock.js ===\n"
        "export const rows1 = [];\n"
        "=== FILE: /App.js ===\n"
        "import Step1 from \"./views/Step1.js\";\n"
        "import { Sidebar, Topbar, ToastHost } from \"./ui\";\n"
        "export default function App(){ return <div />; }\n"
    )

    def empty_view(_prompt):
        # Simulate a view worker that returns {} (empty parse / exception path).
        return ""  # parse_multi_file_response returns {} on empty string

    _install_fakes(monkeypatch, plan, arch, shell_with_orphan_import, empty_view)

    repair_calls = []

    def fake_chat(prompt, **kw):
        repair_calls.append(prompt)
        return (
            "=== FILE: /views/Step1.js ===\n"
            "export default function View(){ return null; }\n"
        )

    monkeypatch.setattr(g, "chat", fake_chat)

    result = g.run_build("x", premium=True, framework="react")

    # Exactly one repair call for the orphan shell import
    assert len(repair_calls) == 1
    # Build did not crash and the view file was filled in
    assert "/views/Step1.js" in result["files"]


def test_ui_import_re_matches_multiline(monkeypatch):
    """Minor #2 — _UI_IMPORT_RE with re.DOTALL matches a multi-line import statement."""
    multiline_import = (
        'import {\n'
        '  Card,\n'
        '  DataTable\n'
        '} from "../ui";\n'
    )
    match = g._UI_IMPORT_RE.search(multiline_import)
    assert match is not None, "_UI_IMPORT_RE must match multi-line import { ... } from '../ui'"
    names = [n.strip() for n in match.group(1).split(",") if n.strip()]
    assert "Card" in names
    assert "DataTable" in names
