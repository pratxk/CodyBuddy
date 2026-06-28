DESIGN_GUIDELINES = """DESIGN REQUIREMENTS (non-negotiable — the app must look modern and polished, not bare HTML):
- ALWAYS include a /styles.css file and import it once at the top of /App.js: import "./styles.css";
- Define CSS custom properties (variables) at :root for the full color token set:
    --color-bg, --color-surface, --color-border, --color-primary, --color-accent,
    --color-text, --color-muted. Use these variables throughout — no raw hex literals.
- Accent: apply a subtle linear-gradient (e.g. 135deg from --color-primary to --color-accent)
  to the page header/hero banner and to primary buttons. Not everywhere — just the focal points.
- Type scale: body 1rem, headings 1.5–2rem, captions/labels 0.8125rem. System font stack.
- Layout — MATCH THE APP TYPE (do NOT cram everything into one tiny card):
    * Simple single-purpose apps (calculator, timer, single game, one form): a centered
      card, max-width ~640px.
    * Data-rich / dashboard / multi-section / tool / SaaS apps: a FULL-WIDTH APP SHELL
      (max-width ~1200–1400px, auto margins) with a real responsive layout — a header/toolbar,
      and a CSS-grid of multiple panels/cards (e.g. grid-template-columns: repeat(auto-fit,
      minmax(260px, 1fr))). Dashboards must have MULTIPLE metric/stat cards AND one or more
      charts AND a data table or list — never a single lonely chart.
  Page bg should differ from card/panel surface.
- DATA VISUALISATION: for any charts/graphs, USE A REAL CHART LIBRARY via npm (Sandpack
  resolves it from CDN) — prefer `recharts` (LineChart/AreaChart/BarChart/PieChart +
  ResponsiveContainer) over hand-drawn divs. Add it to package.json dependencies. Charts must
  be responsive (wrap in ResponsiveContainer) and use the palette tokens.
- RESPONSIVE (required): the app must look good from 320px phones to wide desktops. Use a
  fluid container (width:100%; max-width:Npx; margin:auto) and box-sizing:border-box. Never
  cause horizontal scroll. Build grids/rows with CSS grid/flex that reflow; size cells with
  fr/%/min() (e.g. grid boards: grid-template-columns: repeat(N, 1fr) and aspect-ratio:1 for
  square cells) — never fixed px widths that overflow small screens. Add a @media (max-width:
  480px) block that shrinks padding/font-size and stacks controls vertically. Tap targets ≥40px.
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


def intake_prompt(prompt: str, history: list[dict]) -> str:
    """Build the INTAKE self-gating prompt.

    history is a list of {"question": str, "answer": str} already collected.
    """
    if history:
        history_text = "\n".join(
            f"  Q: {h['question']}\n  A: {h['answer']}" for h in history
        )
    else:
        history_text = "  (none yet)"
    return f"""You are the INTAKE agent for an app generator that builds small React SPAs.
Decide whether the user's request is specific enough to build a good first version.

User's original request: {prompt}

Answers gathered so far:
{history_text}

You are a SENIOR product engineer scoping a build. Ask the sharp, high-leverage questions a
pro would ask before building — but never interrogate past what changes the build.

Decision rules:
- TRIVIAL, well-specified apps → BUILD NOW (ready=true). If it's a small single-purpose app and
  the request already names it, don't ask anything: "tic-tac-toe with score", "a pomodoro timer",
  "a calculator", "a markdown note app", "a todo list" → ready=true, sensible defaults in the brief.
- NON-TRIVIAL apps (dashboards, trackers, tools, SaaS, anything with data / multiple
  views / workflows / users) → ASK 2-4 SHARP questions before building (you have a 5-question
  budget — use what's needed, then build). Each question targets a decision that materially
  changes the app. Examples of GOOD questions (adapt to the request, never ask all generically):
    * Dashboard: "What is this dashboard tracking?" (options: Sales/revenue, Web analytics,
      Server/infra metrics, Crypto/markets) → then "Which KPIs matter most?" → "Static snapshot
      or live-updating in real time?" → "Any key interactions?" (filter by date range, drill into
      a metric, compare periods).
    * Tracker/tool: what's the core entity, what actions, what should the main view show.
  Ask ONE question per turn with 2-4 concrete, short, selectable `options`; build on prior
  answers; never repeat an answered one; don't ask about pure cosmetics (colors/theme) — those
  are refined later by chat.
- Stop asking and set ready=true as soon as you have enough to build a genuinely capable version
  (usually after 2-4 answers for complex apps). When ready, write a RICH `brief` (2-4 sentences)
  that folds in every answer and names the concrete features/metrics/charts/interactions to build.

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "ready": false,
  "question": "What kind of app do you want to build?",
  "options": ["A game", "A productivity tool", "A data dashboard", "A creative toy"],
  "brief": null
}}
OR, when ready:
{{
  "ready": true,
  "question": null,
  "options": [],
  "brief": "Build a tic-tac-toe game with a 3x3 board and a running score for X and O."
}}"""


def planner_prompt(user_prompt: str) -> str:
    return f"""You are the PLANNER for a React app that will run in a CodeSandbox Sandpack
"react" sandbox (CRA-style, entry file is /App.js). Turn the request into a build plan.

User's request: {user_prompt}

Rules:
- Output a CLIENT-SIDE React SPA only (no server, no Node backend, no native deps).
- Entry component MUST be /App.js. Put extra components under /components/.
- ALWAYS include a /styles.css file in the plan (the app must be styled, not bare HTML).
- Use npm packages resolvable from a CDN — react, react-dom, and for data viz prefer
  `recharts`; date-fns for dates; etc. List them in techStack.
- AMBITION: design a genuinely CAPABLE, production-feeling first version — NOT a toy. Decompose
  into several real components (5-9 files is normal for a rich app). For a "dashboard", plan
  MULTIPLE metric cards, 2+ charts (different types), a data table/list, and filters/controls;
  if the user said "real-time", plan simulated live data that updates on an interval. Cover the
  core feature deeply with sensible realistic seed data — a reviewer should think "this is a
  real app", not "this is a demo stub".

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
    "You are the CODER. You implement ALL files of a React app in ONE response, "
    "for a CodeSandbox Sandpack 'react' sandbox (entry /App.js). Use modern function "
    "components and hooks. Use ES module imports/exports. Import sibling files by their "
    "path (e.g. import Board from './components/Board'). /App.js MUST import \"./styles.css\". "
    "Only use CDN-resolvable npm packages. "
    "CRITICAL: EVERY file imported in any component MUST be emitted in this response — "
    "no orphan imports, no missing files. ONE source of truth for state: lift shared state "
    "to App.js and pass props down; never have two components independently owning the same state. "
    "The core feature must WORK and be VISIBLE: games/boards need real CSS grids with sized, "
    "bordered, clickable cells. "
    "CORRECTNESS (avoid runtime crashes): NEVER render an object or array directly as a JSX "
    "child — render primitive fields (e.g. {score.x} and {score.o}, never {score}). Initialize "
    "every state value before use; guard array .map over possibly-undefined data; give list "
    "items stable keys; ensure every onClick/handler and prop the JSX references is defined. "
    "The app must mount and run with NO console errors. "
    "PRODUCE VISUALLY POLISHED UIs: use CSS variables for color tokens, a gradient accent on "
    "header/primary buttons, system font stack, rem-based type scale, comfortable spacing, "
    "rounded corners (12-16px), soft box-shadows, a centered responsive card, smooth "
    "transitions (0.2s ease) on all interactive elements, hover/active states, "
    "focus-visible outlines for accessibility, and a fadeInUp keyframe on the main card. "
    "When writing /styles.css, write real, complete, modern CSS — never empty or placeholder."
)


def coder_prompt(task_steps: list[dict], plan_json: str) -> str:
    """Build the single-call prompt that generates ALL app files at once."""
    steps_text = "\n".join(
        f"  {i+1}. {s['filepath']}: {s['task_description']}"
        for i, s in enumerate(task_steps)
    )
    file_list = ", ".join(s["filepath"] for s in task_steps)
    return f"""Project plan:
{plan_json}

Implementation steps (for ALL files you must produce):
{steps_text}

{DESIGN_GUIDELINES}

FUNCTIONAL COMPLETENESS RULES (non-negotiable):
- App.js MUST render the ENTIRE feature UI — not just a shell.
- EVERY component imported by ANY file must be defined in this response.
- ONE source of truth for app state: lift shared state to App.js and pass props down.
  Components must NOT declare their own duplicate state for data passed as props.

BUILD A CAPABLE, PRODUCTION-FEELING APP — NOT A STUB:
- Implement the FULL feature set from the plan with real interactivity — not a single widget
  with one piece of dummy data. A reviewer should think "this is a real app".
- DASHBOARDS specifically: render MULTIPLE distinct metric/stat cards (with value, label, and
  a delta/trend), 2+ charts of DIFFERENT types via `recharts` (e.g. an area/line trend + a
  bar/pie breakdown, each in <ResponsiveContainer>), AND a data table or list. Add working
  filters/controls (time range, category) that actually filter the rendered data. Seed with
  rich, realistic data (15-30+ points), not 3 dummy rows.
- "REAL-TIME": simulate live data with a useEffect setInterval that updates state every
  1-2s (append a new point, shift the window, recompute metrics); clear the interval on
  unmount. Add a subtle "live" pulse indicator.
- GAMES/grids: CSS Grid with sized bordered clickable cells (font-size:2rem+ for marks);
  real win/score logic wired to outcomes — a real playable board, not text.
- Charts via recharts must be wrapped in <ResponsiveContainer width="100%" height={...}> and
  use the palette tokens; add recharts to /package.json dependencies.

Output ALL {len(task_steps)} files in this EXACT format — no prose before/after, no markdown fences around the file delimiter lines:

=== FILE: /styles.css ===
(full file body here)
=== FILE: /App.js ===
(full file body here)

Files to emit (in dependency order — dependencies before consumers): {file_list}

Use EXACTLY the delimiter format above for each file. No other text outside the delimiters."""


def oncall_prompt(files: dict[str, str], error: str) -> str:
    """Build the OnCallAgent single-call prompt.

    ponytail: delegates to vibe_prompt so file-embedding + format rules are DRY.
    The instruction is an error-fix directive that asks for root-cause analysis.
    """
    instruction = (
        f"FIX RUNTIME/COMPILE ERROR — diagnose the ROOT CAUSE then return the COMPLETE "
        f"corrected file set (all files, not just the changed ones).\n\n"
        f"Error:\n{error}"
    )
    return vibe_prompt(files, instruction)


def vibe_prompt(files: dict[str, str], instruction: str) -> str:
    """Build the single-call VibeEngineer prompt.

    Embeds current files (=== FILE: === blocks) + instruction and asks for
    the COMPLETE updated file set in the same delimited format.
    """
    current_files_text = "\n".join(
        f"=== FILE: {path} ===\n{content}" for path, content in files.items()
    )
    file_list = ", ".join(files.keys())
    return f"""You are the VIBE ENGINEER for a React app running in a CodeSandbox Sandpack 'react' sandbox.

The user wants to modify the existing app with the following instruction:
{instruction}

Current app files:
{current_files_text}

{DESIGN_GUIDELINES}

RULES:
- Apply the instruction FULLY and AMBITIOUSLY. If the user asks to "add features" or "enhance"
  or "make it real-time", implement substantial, complete functionality — add new components,
  charts, interactions, state and realistic data as needed; do NOT do the bare minimum (e.g.
  don't answer "enhance this dashboard" with just one date filter). Match the depth a senior
  engineer would ship. New chart needs → use recharts (add to package.json). Real-time →
  setInterval-updating state cleaned up on unmount.
- Keep ALL other files intact and coherent — no missing imports, no broken references.
- The result must be a working Sandpack react app (entry /App.js) that mounts with NO errors.
- Maintain/raise design quality per DESIGN_GUIDELINES (app-appropriate layout, not a tiny card
  for a data app; responsive; polished).
- Emit EVERY file (modified or unchanged) so the full file set is complete.

Output ALL files in this EXACT format — no prose before/after, no markdown fences:

=== FILE: /styles.css ===
(full file body here)
=== FILE: /App.js ===
(full file body here)

Files to emit (all of them, in dependency order): {file_list}

Use EXACTLY the delimiter format above for each file. No other text outside the delimiters."""
