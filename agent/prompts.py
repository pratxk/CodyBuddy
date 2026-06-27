def planner_prompt(user_prompt: str) -> str:
    return f"""You are the PLANNER for a React app that will run in a CodeSandbox Sandpack
"react" sandbox (CRA-style, entry file is /App.js). Turn the request into a build plan.

User's request: {user_prompt}

Rules:
- Output a CLIENT-SIDE React SPA only (no server, no Node backend, no native deps).
- Entry component MUST be /App.js. Put extra components under /components/.
- Use only npm packages resolvable from a CDN (e.g. react, react-dom, common UI libs).
- Keep it minimal but complete.

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "name": "App Name",
  "description": "one-line description",
  "techStack": ["React", "..."],
  "features": ["feature 1", "feature 2"],
  "files": [
    {{"path": "/App.js", "purpose": "root component"}},
    {{"path": "/components/Board.js", "purpose": "..."}}
  ]
}}"""


def architect_prompt(plan_json: str) -> str:
    return f"""You are the ARCHITECT. Break the plan into ordered, self-contained
implementation steps — one per file.

For each step specify exactly what to implement (component names, props, state, handlers)
and how files connect (imports/exports). /App.js imports the components. Order dependencies
first. Each step must be self-contained.

Project plan (JSON):
{plan_json}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "implementation_steps": [
    {{"filepath": "/components/Board.js", "task_description": "detailed instructions"}},
    {{"filepath": "/App.js", "task_description": "imports and composes components"}}
  ]
}}"""


CODER_SYSTEM_PROMPT = (
    "You are the CODER. You implement one React file at a time, completely and correctly, "
    "for a CodeSandbox Sandpack 'react' sandbox (entry /App.js). Use modern function "
    "components and hooks. Use ES module imports/exports. Import sibling files by their "
    "path (e.g. import Board from './components/Board'). Only use CDN-resolvable npm "
    "packages. Never reference files that do not exist in the plan."
)


def coder_prompt(task_description: str, filepath: str, existing_content: str, plan_json: str) -> str:
    existing = existing_content if existing_content else "(file does not exist yet)"
    return f"""Project plan (for context):
{plan_json}

Implement this file for a Sandpack 'react' sandbox:
- File: {filepath}
- Task: {task_description}

Existing content:
{existing}

Output the COMPLETE final contents of {filepath} and NOTHING else.
No commentary, no explanations, no markdown code fences — just the raw file body."""
