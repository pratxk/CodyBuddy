def planner_prompt(user_prompt: str) -> str:
    return f"""You are the PLANNER agent. Turn the user's request into a concrete build plan.

User's request: {user_prompt}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "name": "App Name",
  "description": "one-line description",
  "techStack": ["e.g. HTML", "CSS", "JavaScript"],
  "features": ["feature 1", "feature 2"],
  "files": [
    {{"path": "index.html", "purpose": "what this file is for"}}
  ]
}}

Rules:
- Keep it minimal but complete — list every file the app needs to run.
- Prefer simple, dependency-free stacks unless the user asks otherwise.
- Do NOT include file contents here; only path + purpose."""


def architect_prompt(plan_json: str) -> str:
    return f"""You are the ARCHITECT agent. Break the plan into ordered, self-contained
implementation steps — one per file.

For each step:
- Specify exactly what to implement: variables, functions, classes, components.
- Note how it integrates with other files: imports, expected signatures, data flow.
- Order steps so dependencies are implemented first.

Project plan (JSON):
{plan_json}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "implementation_steps": [
    {{"filepath": "index.html", "task_description": "detailed, self-contained instructions"}}
  ]
}}"""


CODER_SYSTEM_PROMPT = (
    "You are the CODER agent. You implement one file at a time, completely and correctly. "
    "You write production-quality code that integrates cleanly with the other files in the project. "
    "Maintain consistent naming of variables, functions, and imports across files."
)


def coder_prompt(task_description: str, filepath: str, existing_content: str, plan_json: str) -> str:
    existing = existing_content if existing_content else "(file does not exist yet)"
    return f"""Project plan (for context):
{plan_json}

Implement this file:
- File: {filepath}
- Task: {task_description}

Existing content:
{existing}

Output the COMPLETE final contents of {filepath} and NOTHING else.
No commentary, no explanations, no markdown code fences — just the raw file body."""
