import logging
import re
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.llm import (CODER_CHAIN, CODER_CHAIN_PREMIUM, PLANNER_CHAIN, chat,
                       chat_stream, chat_structured, strip_code_fences)
from agent.premium_scaffold import PREMIUM_SCAFFOLD_FILES
from agent.prompts import (architect_prompt, coder_prompt, coder_shell_prompt,
                           coder_system_prompt, coder_view_prompt, oncall_prompt,
                           planner_prompt, premium_architect_prompt,
                           premium_coder_system_prompt, premium_planner_prompt)
from agent.scaffold import (coerce_framework, ensure_dependencies,
                           normalize_files, parse_multi_file_response)
from agent.states import Plan, PremiumArchitecture, PremiumPlan, TaskPlan

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("codybuddy")


def _planner_node(emitter, premium=False, framework="react"):
    def node(state: dict) -> dict:
        # ponytail: generous budget — reasoning-model fallbacks (Cerebras gpt-oss, GLM)
        # spend tokens thinking, so a tight cap truncates the JSON ("Unterminated string").
        plan = chat_structured(planner_prompt(state["user_prompt"], premium=premium, framework=framework),
                               Plan, chain=PLANNER_CHAIN, max_tokens=6000 if premium else 4000)
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan}
    return node


def _architect_node(emitter, premium=False, framework="react"):
    def node(state: dict) -> dict:
        plan: Plan = state["plan"]
        # ponytail: 10000 — richer apps = more files/steps in the TaskPlan JSON; premium plans
        # are bigger (8-14 files), so give them 16000.
        task_plan = chat_structured(
            architect_prompt(plan.model_dump_json(indent=2), premium=premium, framework=framework),
            TaskPlan, chain=PLANNER_CHAIN, max_tokens=16000 if premium else 10000)
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan, "task_plan": task_plan, "plan_json": plan.model_dump_json()}
    return node


def _coder_node(emitter, premium=False, framework="react"):
    def node(state: dict) -> dict:
        steps = state["task_plan"].implementation_steps
        plan_json = state["plan_json"]
        # ponytail: single LLM call — model sees all files together → coherent imports + state
        task_dicts = [{"filepath": t.filepath, "task_description": t.task_description}
                      for t in steps]
        # ponytail: 14000 lets the coder build rich, multi-component apps (dashboards w/ charts).
        # This exceeds Groq's 12k TPM, so CODER_CHAIN leads with Cerebras (high TPM, 1M/day) —
        # Groq stays a late fallback (it'll 413 on this size and fall through).
        # Premium: 20000 tokens + CODER_CHAIN_PREMIUM (no Groq/OpenRouter) for production-grade apps.
        chain = CODER_CHAIN_PREMIUM if premium else CODER_CHAIN
        max_tokens = 20000 if premium else 14000
        # ponytail: stream the first provider so the FE can show files being written live
        # (coder_chunk events); chat_stream falls back to non-streaming chat() on any hiccup,
        # and we parse the FULL accumulated text exactly as before (final result is authoritative).
        on_delta = emitter.chunk if emitter else None
        raw = chat_stream(coder_prompt(task_dicts, plan_json, premium=premium, framework=framework),
                          chain=chain, system=coder_system_prompt(framework),
                          max_tokens=max_tokens, on_delta=on_delta)
        files = parse_multi_file_response(raw, strip_code_fences)
        for path in files:
            logger.info("Coder: wrote %s (%d chars)", path, len(files[path]))
        if emitter:
            emitter.end_current(ok=True)
        return {"plan": state["plan"], "files": normalize_files(files, framework)}
    return node


def build_graph(emitter=None, premium=False, framework="react"):
    graph = StateGraph(dict)
    graph.add_node("planner", _planner_node(emitter, premium, framework))
    graph.add_node("architect", _architect_node(emitter, premium, framework))
    graph.add_node("coder", _coder_node(emitter, premium, framework))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", END)
    return graph.compile()


def run_build(user_prompt: str, emitter=None, premium: bool = False,
              framework: str = "react") -> dict:
    framework = coerce_framework(framework)
    if emitter:
        emitter.graph_init(); emitter.start_next()
    # ponytail: premium react → the multi-pass dashboard subgraph (shell + parallel views +
    # assemble/validate). Everything else (standard, or premium static/nextjs) → the existing
    # linear graph, byte-for-byte, so the standard path is untouched.
    if premium and framework == "react":
        result = build_premium_graph(emitter).invoke({"user_prompt": user_prompt})
    else:
        # ponytail: premium + framework are baked into the node closures (prompt + budget + shape).
        result = build_graph(emitter, premium, framework).invoke({"user_prompt": user_prompt})
    return {"plan": result["plan"], "files": result["files"], "framework": framework}


# ── Premium multi-pass subgraph ───────────────────────────────────────────────
# planner(premium) → architect(premium) → coder_shell → coder_views(fan-out) →
# assemble(validate+repair) → END. Guarded by run_build to premium AND react only.

# ponytail: cap the workflow at ~6 sidebar steps — bounds worst-case tokens/latency and keeps
# the sidebar readable. Trim if the planner over-produces.
MAX_PREMIUM_VIEWS = 6

# ponytail: views are independent → fan out on a small module-level pool (concurrency cap 3).
# Each call falls through CODER_CHAIN_PREMIUM on its own; 3 keeps us inside per-minute limits.
_VIEW_POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="premium-view")

# The primitives the baked /ui barrel actually exports — the coherence validator flags any
# named import from ../ui outside this set as an orphan (drift = runtime crash).
_UI_EXPORTS: frozenset[str] = frozenset({
    "Card", "KPIStat", "DataTable", "Badge", "Button", "Sidebar", "Topbar",
    "Tabs", "ProgressBar", "Modal", "Toast", "ToastHost", "useToast",
})

_UI_IMPORT_RE = re.compile(r"""import\s*\{([^}]*)\}\s*from\s*['"](?:\.\.?/)*ui['"]""")
_VIEW_IMPORT_RE = re.compile(r"""from\s*['"]((?:\.\.?/)*views/[^'"]+)['"]""")


def _premium_planner_node(emitter):
    def node(state: dict) -> dict:
        # ponytail: generous budget — the domain plan (views + kpis + columns + mock story) is
        # sizeable; a tight cap truncates the JSON. Cap views AFTER validation (immutable copy).
        plan: PremiumPlan = chat_structured(
            premium_planner_prompt(state["user_prompt"]), PremiumPlan,
            chain=PLANNER_CHAIN, max_tokens=6000)
        if len(plan.views) > MAX_PREMIUM_VIEWS:
            plan = plan.model_copy(update={"views": plan.views[:MAX_PREMIUM_VIEWS]})
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan}
    return node


def _premium_architect_node(emitter):
    def node(state: dict) -> dict:
        plan: PremiumPlan = state["plan"]
        arch: PremiumArchitecture = chat_structured(
            premium_architect_prompt(plan.model_dump_json()), PremiumArchitecture,
            chain=PLANNER_CHAIN, max_tokens=16000)
        # ponytail: never emit more views than the plan has steps (bound to the cap).
        if len(arch.view_specs) > len(plan.views):
            arch = arch.model_copy(update={"view_specs": arch.view_specs[:len(plan.views)]})
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan, "architecture": arch, "plan_json": plan.model_dump_json()}
    return node


def _coder_shell_node(emitter):
    def node(state: dict) -> dict:
        arch: PremiumArchitecture = state["architecture"]
        on_delta = emitter.chunk if emitter else None
        raw = chat_stream(coder_shell_prompt(state["plan_json"], arch.mock_schema),
                          chain=CODER_CHAIN_PREMIUM, system=premium_coder_system_prompt(),
                          max_tokens=12000, on_delta=on_delta)
        shell_files = parse_multi_file_response(raw, strip_code_fences)
        for path in shell_files:
            logger.info("Shell coder: wrote %s (%d chars)", path, len(shell_files[path]))
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {**state, "shell_files": shell_files}
    return node


def _coder_view_node(spec, palette: dict, on_delta):
    """Generate ONE /views/<View>.js from its architect spec. Runs in a worker thread;
    a bad/emptyparse for a single view returns {} rather than crashing the whole build."""
    try:
        raw = chat_stream(coder_view_prompt(spec.model_dump_json(), spec.data_keys, palette),
                          chain=CODER_CHAIN_PREMIUM, system=premium_coder_system_prompt(),
                          max_tokens=8000, on_delta=on_delta)
        return parse_multi_file_response(raw, strip_code_fences)
    except Exception as exc:  # noqa: BLE001  ponytail: one view failing must not sink the build
        logger.warning("View coder failed for %s: %s", getattr(spec, "filepath", "?"), exc)
        return {}


def _coder_views_node(emitter):
    def node(state: dict) -> dict:
        plan: PremiumPlan = state["plan"]
        specs = state["architecture"].view_specs
        on_delta = emitter.chunk if emitter else None
        # ponytail: fan out the N view calls in parallel (cap 3) — cuts latency vs sequential.
        results = list(_VIEW_POOL.map(
            lambda s: _coder_view_node(s, plan.palette, on_delta), specs))
        view_files: dict[str, str] = {}
        for files in results:
            view_files.update(files)
        for path in view_files:
            logger.info("View coder: wrote %s (%d chars)", path, len(view_files[path]))
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {**state, "view_files": view_files}
    return node


def _norm_path(path: str) -> str:
    return path if path.startswith("/") else "/" + path


def _coherence_errors(content: str, files: dict[str, str]) -> list[str]:
    """Lightweight static coherence check for one generated file (NOT a real parser):
    - a named import from ../ui that the baked barrel does not export (orphan primitive)
    - an import of a /views/* file that was not generated (orphan view import)
    Returns a list of human-readable issues (empty = coherent).
    """
    if not isinstance(content, str):
        return []
    errors: list[str] = []
    for match in _UI_IMPORT_RE.finditer(content):
        for raw_name in match.group(1).split(","):
            name = raw_name.strip()
            if not name:
                continue
            # handle `Foo as Bar` / `default as Foo` — the imported binding is the FIRST token.
            base = name.split()[0]
            if base and base not in _UI_EXPORTS:
                errors.append(f"imports '{base}' from ../ui which the primitive kit does not export")
    for match in _VIEW_IMPORT_RE.finditer(content):
        src = match.group(1)
        tail = src.split("views/", 1)[1]
        target = "/views/" + (tail if tail.endswith(".js") else tail + ".js")
        if target not in files:
            errors.append(f"imports view '{target}' which was not generated")
    return errors


def _repair_view(path: str, content: str, error: str) -> str | None:
    """ONE targeted repair pass for a single offending view (reuse oncall_prompt shape over the
    premium coder chain). Returns the repaired body, or None if it couldn't be parsed."""
    try:
        raw = chat(oncall_prompt({path: content}, error), chain=CODER_CHAIN_PREMIUM,
                   system=premium_coder_system_prompt(), max_tokens=8000)
        repaired = parse_multi_file_response(raw, strip_code_fences)
        return repaired.get(path) or repaired.get(_norm_path(path))
    except Exception as exc:  # noqa: BLE001  ponytail: a failed repair must not crash the build
        logger.warning("Repair pass for %s failed: %s", path, exc)
        return None


def _validate_and_repair(files: dict[str, str], view_specs) -> dict[str, str]:
    """Scan each generated view for coherence issues; on failure do ONE targeted repair call.
    If the repair still doesn't resolve it, keep the original (best available) and log — the
    build never crashes on a coherence miss."""
    out = dict(files)
    for spec in view_specs:
        path = _norm_path(spec.filepath)
        content = out.get(path)
        if content is None:
            continue
        errors = _coherence_errors(content, out)
        if not errors:
            continue
        logger.warning("Coherence issues in %s: %s", path, "; ".join(errors))
        repaired = _repair_view(path, content, "; ".join(errors))
        if repaired and not _coherence_errors(repaired, {**out, path: repaired}):
            out[path] = repaired
            logger.info("Repair healed %s", path)
        else:
            logger.warning("Repair did not resolve %s — keeping best version", path)
    return out


def _assemble_node(emitter):
    def node(state: dict) -> dict:
        plan: PremiumPlan = state["plan"]
        # ponytail: baked scaffold FIRST, then shell, then views — later keys win on overlap,
        # but the coder is told not to re-emit scaffold files so overlap should be none.
        merged = {**PREMIUM_SCAFFOLD_FILES, **state["shell_files"], **state["view_files"]}
        files = normalize_files(merged, "react")
        files = ensure_dependencies(files)  # backfill lucide-react/recharts (idempotent)
        files = _validate_and_repair(files, state["architecture"].view_specs)
        for path in files:
            logger.info("Assembled: %s (%d chars)", path, len(files[path]) if isinstance(files[path], str) else 0)
        if emitter:
            emitter.end_current(ok=True)
        return {"plan": plan, "files": files}
    return node


def build_premium_graph(emitter=None):
    graph = StateGraph(dict)
    graph.add_node("planner", _premium_planner_node(emitter))
    graph.add_node("architect", _premium_architect_node(emitter))
    graph.add_node("shell", _coder_shell_node(emitter))
    graph.add_node("views", _coder_views_node(emitter))
    graph.add_node("assemble", _assemble_node(emitter))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "shell")
    graph.add_edge("shell", "views")
    graph.add_edge("views", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()
