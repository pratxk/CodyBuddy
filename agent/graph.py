import logging

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.llm import CODER_CHAIN, PLANNER_CHAIN, chat, chat_structured, strip_code_fences
from agent.prompts import (CODER_SYSTEM_PROMPT, architect_prompt,
                           coder_prompt, planner_prompt)
from agent.scaffold import normalize_files, parse_multi_file_response
from agent.states import Plan, TaskPlan

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("codybuddy")


def _planner_node(emitter):
    def node(state: dict) -> dict:
        plan = chat_structured(planner_prompt(state["user_prompt"]), Plan,
                               chain=PLANNER_CHAIN, max_tokens=1500)
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan}
    return node


def _architect_node(emitter):
    def node(state: dict) -> dict:
        plan: Plan = state["plan"]
        task_plan = chat_structured(architect_prompt(plan.model_dump_json(indent=2)),
                                    TaskPlan, chain=PLANNER_CHAIN, max_tokens=2000)
        if emitter:
            emitter.end_current(ok=True); emitter.start_next()
        return {"plan": plan, "task_plan": task_plan, "plan_json": plan.model_dump_json()}
    return node


def _coder_node(emitter):
    def node(state: dict) -> dict:
        steps = state["task_plan"].implementation_steps
        plan_json = state["plan_json"]
        # ponytail: single LLM call — model sees all files together → coherent imports + state
        task_dicts = [{"filepath": t.filepath, "task_description": t.task_description}
                      for t in steps]
        raw = chat(coder_prompt(task_dicts, plan_json),
                   chain=CODER_CHAIN, system=CODER_SYSTEM_PROMPT, max_tokens=16384)
        files = parse_multi_file_response(raw, strip_code_fences)
        for path in files:
            logger.info("Coder: wrote %s (%d chars)", path, len(files[path]))
        if emitter:
            emitter.end_current(ok=True)
        return {"plan": state["plan"], "files": normalize_files(files)}
    return node


def build_graph(emitter=None):
    graph = StateGraph(dict)
    graph.add_node("planner", _planner_node(emitter))
    graph.add_node("architect", _architect_node(emitter))
    graph.add_node("coder", _coder_node(emitter))
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", END)
    return graph.compile()


def run_build(user_prompt: str, emitter=None) -> dict:
    if emitter:
        emitter.graph_init(); emitter.start_next()
    result = build_graph(emitter).invoke({"user_prompt": user_prompt})
    return {"plan": result["plan"], "files": result["files"]}
