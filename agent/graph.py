import logging

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.llm import (CODER_CHAIN, CODER_CHAIN_PREMIUM, PLANNER_CHAIN,
                       chat_stream, chat_structured, strip_code_fences)
from agent.prompts import (architect_prompt, coder_prompt, coder_system_prompt,
                           planner_prompt)
from agent.scaffold import (coerce_framework, normalize_files,
                           parse_multi_file_response)
from agent.states import Plan, TaskPlan

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
    # ponytail: premium + framework are baked into the node closures (prompt + token budget + shape).
    result = build_graph(emitter, premium, framework).invoke({"user_prompt": user_prompt})
    return {"plan": result["plan"], "files": result["files"], "framework": framework}
