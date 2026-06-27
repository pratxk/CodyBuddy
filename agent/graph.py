import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.llm import CODER_CHAIN, PLANNER_CHAIN, chat, chat_structured
from agent.prompts import (CODER_SYSTEM_PROMPT, architect_prompt,
                           coder_prompt, planner_prompt)
from agent.scaffold import normalize_files
from agent.states import ImplementationTask, Plan, TaskPlan
from agent.llm import strip_code_fences

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("codybuddy")

MAX_CONCURRENCY = 6


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


def _code_one(task: ImplementationTask, plan_json: str) -> tuple[str, str]:
    raw = chat(coder_prompt(task.task_description, task.filepath, "", plan_json),
               chain=CODER_CHAIN, system=CODER_SYSTEM_PROMPT, max_tokens=4096)
    return task.filepath, strip_code_fences(raw)


def _coder_node(emitter):
    def node(state: dict) -> dict:
        steps = state["task_plan"].implementation_steps
        plan_json = state["plan_json"]
        files: dict[str, str] = {}
        workers = min(MAX_CONCURRENCY, max(1, len(steps)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_code_one, t, plan_json): t for t in steps}
            for fut in as_completed(futures):
                try:
                    path, content = fut.result()
                    files[path] = content
                    logger.info("Coder: wrote %s", path)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Coder: failed %s — %s", futures[fut].filepath, exc)
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


if __name__ == "__main__":
    out = run_build("Build a tic-tac-toe game")
    print("files:", list(out["files"].keys()))
