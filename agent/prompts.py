DESIGN_GUIDELINES = """DESIGN REQUIREMENTS (non-negotiable — the app must look polished, not bare HTML):
- ALWAYS include a /styles.css file and import it once at the top of /App.js: import "./styles.css";
- Modern, attractive visual design: a cohesive color palette (a clear accent color), a
  system font stack, generous spacing, rounded corners (8-16px), and subtle shadows.
- Center the main UI in a card/container with comfortable padding; make it responsive.
- Style EVERY interactive element: buttons get padding, accent background, hover and
  active states, and a pointer cursor; inputs get borders/focus states.
- Use readable font sizes and clear visual hierarchy (heading, body, controls).
- Prefer a clean light or tasteful dark theme. Avoid unstyled default browser elements.
- Do not rely on external CSS frameworks/CDNs for styling — write real CSS in /styles.css."""


def planner_prompt(user_prompt: str) -> str:
    return f"""You are the PLANNER for a React app that will run in a CodeSandbox Sandpack
"react" sandbox (CRA-style, entry file is /App.js). Turn the request into a build plan.

User's request: {user_prompt}

Rules:
- Output a CLIENT-SIDE React SPA only (no server, no Node backend, no native deps).
- Entry component MUST be /App.js. Put extra components under /components/.
- ALWAYS include a /styles.css file in the plan (the app must be styled, not bare HTML).
- Use only npm packages resolvable from a CDN (e.g. react, react-dom, common UI libs).
- Keep the feature scope minimal but the UI visually polished and complete.

{DESIGN_GUIDELINES}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "name": "App Name",
  "description": "one-line description",
  "techStack": ["React", "CSS"],
  "features": ["feature 1", "feature 2"],
  "files": [
    {{"path": "/App.js", "purpose": "root component; imports ./styles.css"}},
    {{"path": "/styles.css", "purpose": "modern, polished styling for the whole app"}},
    {{"path": "/components/Board.js", "purpose": "..."}}
  ]
}}"""


def architect_prompt(plan_json: str) -> str:
    return f"""You are the ARCHITECT. Break the plan into ordered, self-contained
implementation steps — one per file.

For each step specify exactly what to implement (component names, props, state, handlers)
and how files connect (imports/exports). /App.js imports the components AND imports
"./styles.css". The /styles.css step must describe concrete, attractive styling (palette,
layout, button/input states) — not a placeholder. Order dependencies first. Each step
must be self-contained.

{DESIGN_GUIDELINES}

Project plan (JSON):
{plan_json}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "implementation_steps": [
    {{"filepath": "/styles.css", "task_description": "concrete modern styling: ..."}},
    {{"filepath": "/components/Board.js", "task_description": "detailed instructions"}},
    {{"filepath": "/App.js", "task_description": "imports ./styles.css and composes components"}}
  ]
}}"""


CODER_SYSTEM_PROMPT = (
    "You are the CODER. You implement one React file at a time, completely and correctly, "
    "for a CodeSandbox Sandpack 'react' sandbox (entry /App.js). Use modern function "
    "components and hooks. Use ES module imports/exports. Import sibling files by their "
    "path (e.g. import Board from './components/Board'). /App.js MUST import \"./styles.css\". "
    "Only use CDN-resolvable npm packages. Never reference files that do not exist in the plan. "
    "PRODUCE VISUALLY POLISHED UIs: a cohesive color palette with an accent color, system "
    "font stack, generous spacing, rounded corners, subtle shadows, a centered responsive "
    "card layout, and styled buttons/inputs with hover/active/focus states. When the file is "
    "/styles.css, write real, complete, attractive CSS — never an empty or placeholder file."
)


def coder_prompt(task_description: str, filepath: str, existing_content: str, plan_json: str) -> str:
    existing = existing_content if existing_content else "(file does not exist yet)"
    return f"""Project plan (for context):
{plan_json}

Implement this file for a Sandpack 'react' sandbox:
- File: {filepath}
- Task: {task_description}

{DESIGN_GUIDELINES}

Reminders:
- If this is /App.js, include: import "./styles.css"; near the top.
- If this is /styles.css, write complete, attractive, modern CSS covering layout, the
  container/card, typography, and every button/input with hover/active/focus states.

Existing content:
{existing}

Output the COMPLETE final contents of {filepath} and NOTHING else.
No commentary, no explanations, no markdown code fences — just the raw file body."""
