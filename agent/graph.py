"""
CodyBuddy build agent — planner → architect → coder (LangGraph).

Speed + reliability design:
  * OpenAI-compatible client (Groq by default — fast LPU inference), no Modal cold starts.
  * JSON-prompt + robust parse + validation-retry instead of `with_structured_output`.
  * Coder fans out ALL files CONCURRENTLY (ThreadPoolExecutor) instead of looping one
    file at a time — wall-clock ≈ slowest single file, not the sum.
  * Coder emits the raw file body (no fragile JSON wrapper around source code).
  * Bounded `max_tokens` on every call.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agent.llm import (
    CODER_MODEL,
    PLANNER_MODEL,
    chat,
    chat_structured,
    strip_code_fences,
)
from agent.prompts import (
    CODER_SYSTEM_PROMPT,
    architect_prompt,
    coder_prompt,
    planner_prompt,
)
from agent.states import ImplementationTask, Plan, TaskPlan
from agent.tools import init_project_root, read_file, write_file

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("codybuddy")

# Concurrency cap for parallel file generation (keeps us under provider rate limits).
MAX_CONCURRENCY = 6


def planner_agent(state: dict) -> dict:
    logger.info("Planner: generating build plan…")
    plan: Plan = chat_structured(
        planner_prompt(state["user_prompt"]),
        Plan,
        model=PLANNER_MODEL,
        max_tokens=1500,
    )
    logger.info("Planner: %s — %d file(s)", plan.name, len(plan.files))
    return {"plan": plan}


def architect_agent(state: dict) -> dict:
    logger.info("Architect: breaking plan into implementation steps…")
    plan: Plan = state["plan"]
    task_plan: TaskPlan = chat_structured(
        architect_prompt(plan.model_dump_json(indent=2)),
        TaskPlan,
        model=PLANNER_MODEL,
        max_tokens=2000,
    )
    logger.info("Architect: %d step(s)", len(task_plan.implementation_steps))
    return {"task_plan": task_plan, "plan_json": plan.model_dump_json()}


def _code_one_file(task: ImplementationTask, plan_json: str) -> tuple[str, bool, str]:
    """Generate and write a single file. Returns (filepath, ok, message)."""
    try:
        existing = read_file.invoke({"path": task.filepath})
        raw = chat(
            coder_prompt(task.task_description, task.filepath, existing, plan_json),
            model=CODER_MODEL,
            system=CODER_SYSTEM_PROMPT,
            max_tokens=4096,
        )
        write_file.invoke({"path": task.filepath, "content": strip_code_fences(raw)})
        return task.filepath, True, "ok"
    except Exception as exc:  # noqa: BLE001 — isolate per-file failures
        logger.error("Coder: FAILED %s — %s", task.filepath, exc)
        return task.filepath, False, str(exc)


def coder_agent(state: dict) -> dict:
    """Generate every file in the task plan concurrently."""
    steps = state["task_plan"].implementation_steps
    plan_json = state["plan_json"]
    logger.info("Coder: generating %d file(s) with up to %d workers…", len(steps), MAX_CONCURRENCY)

    results: list[tuple[str, bool, str]] = []
    workers = min(MAX_CONCURRENCY, max(1, len(steps)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_code_one_file, task, plan_json): task for task in steps}
        for future in as_completed(futures):
            filepath, ok, msg = future.result()
            results.append((filepath, ok, msg))
            logger.info("Coder: %s %s", "✓" if ok else "✗", filepath)

    failed = [fp for fp, ok, _ in results if not ok]
    if failed:
        logger.warning("Coder: %d/%d file(s) failed: %s", len(failed), len(steps), failed)
    return {"results": results}


def build_graph():
    graph = StateGraph(dict)
    graph.add_node("planner", planner_agent)
    graph.add_node("architect", architect_agent)
    graph.add_node("coder", coder_agent)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "architect")
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", END)
    return graph.compile()


agent = build_graph()


def run(user_prompt: str) -> dict:
    """Run the full build pipeline for a single user request."""
    project_root = init_project_root()
    logger.info("Output directory: %s", project_root)
    result = agent.invoke({"user_prompt": user_prompt})
    logger.info("Done. Files written under %s", project_root)
    return result


if __name__ == "__main__":
    final = run("Build a colourful calculator app in html css and js")
    print(json.dumps({"plan": final["plan"].name, "results": final.get("results")}, indent=2))
