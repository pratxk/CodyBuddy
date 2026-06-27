DESIGN_GUIDELINES = """DESIGN REQUIREMENTS (non-negotiable — the app must look modern and polished, not bare HTML):
- ALWAYS include a /styles.css file and import it once at the top of /App.js: import "./styles.css";
- Define CSS custom properties (variables) at :root for the full color token set:
    --color-bg, --color-surface, --color-border, --color-primary, --color-accent,
    --color-text, --color-muted. Use these variables throughout — no raw hex literals.
- Accent: apply a subtle linear-gradient (e.g. 135deg from --color-primary to --color-accent)
  to the page header/hero banner and to primary buttons. Not everywhere — just the focal points.
- Type scale: body 1rem, headings 1.5–2rem, captions/labels 0.8125rem. System font stack.
- Layout: center the main UI in a card/container (max-width ~640px, auto margins, comfortable
  padding 1.5–2rem). Page bg should differ from card surface. Responsive with no horizontal scroll.
- Depth & polish: card gets box-shadow (0 4px 24px rgba(0,0,0,.08)), border-radius 12–16px.
  Inputs get a 1px border, border-radius 8px, and 0.75rem padding.
- Smooth transitions: all interactive elements (buttons, inputs, links) get
  transition: all 0.2s ease so hover/focus feel snappy, not instant.
- Hover/active states: buttons darken or shift gradient on :hover; scale(0.97) on :active.
- Accessibility: every focusable element gets a visible :focus-visible outline
  (outline: 2px solid var(--color-accent); outline-offset: 2px; border-radius: 4px).
- Subtle entrance animation: @keyframes fadeInUp { from { opacity:0; transform:translateY(12px) }
  to { opacity:1; transform:translateY(0) } } applied to the main card/container
  (animation: fadeInUp 0.35s ease both).
- Choose either a clean light theme or a tasteful dark theme that suits the app's purpose.
  Avoid unstyled browser defaults. Write REAL, complete CSS — never empty or placeholder."""


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
    "PRODUCE VISUALLY POLISHED UIs: use CSS variables for color tokens, a gradient accent on "
    "header/primary buttons, system font stack, rem-based type scale, comfortable spacing, "
    "rounded corners (12-16px), soft box-shadows, a centered responsive card, smooth "
    "transitions (0.2s ease) on all interactive elements, hover/active states, "
    "focus-visible outlines for accessibility, and a fadeInUp keyframe on the main card. "
    "When the file is /styles.css, write real, complete, modern CSS — never empty or placeholder."
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
