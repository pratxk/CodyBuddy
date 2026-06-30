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


PREMIUM_GUIDELINES = """PREMIUM PRODUCTION-GRADE MODE (this build must look like a real, shippable SaaS product — not a demo):
- Build a real MULTI-VIEW PRODUCT SHELL: a persistent SIDEBAR (navigates between sections) plus a
  TOPBAR (app/brand name, search, user avatar/menu). Several DISTINCT sections/pages (e.g. Overview,
  Analytics, a primary entity list/table, Settings) switched via in-app navigation (React state).
- Multiple RICH components: KPI/stat cards with value + label + delta/trend, a sortable/filterable
  DATA TABLE, entity/account CARDS, a CALENDAR or schedule view, plus modals/drawers, tabs, toasts.
- REAL data-viz via `recharts`: at least 2-3 DIFFERENT chart types (area/line trend, bar breakdown,
  pie/donut), each in <ResponsiveContainer>, fed by REALISTIC seed data (weeks of points, dozens of
  rows) that tells a coherent story — keep seed data in its own /data module.
- Concrete example to match in ambition (adapt to the actual request): a Social Media Management
  dashboard with a scheduled-posts table, engagement-over-time charts, connected-account cards, and
  a content calendar.
- EMPTY, LOADING, and HOVER/active states everywhere; interactions must actually work (filters
  filter, tabs switch, sort sorts, modals open/close).
- A cohesive PROFESSIONAL DESIGN SYSTEM: consistent spacing scale, a refined token palette, clear
  typographic hierarchy, subtle motion — on par with Linear / Vercel / Stripe dashboards.
- Target 8-14 well-separated files (App shell + sidebar/topbar + multiple section components +
  chart components + a seed-data module + styles). Do NOT collapse it into one or two big files."""


# ── Framework selection ──────────────────────────────────────────────────────
# The intake reasons about which app shape to build. Values must match
# agent.scaffold.FRAMEWORKS exactly: "react" (default) | "static" | "nextjs".

FRAMEWORK_SELECTION_RULE = """FRAMEWORK CHOICE — pick exactly one of "react" | "static" | "nextjs":
- "react" (DEFAULT): use for almost everything — a normal request like "a tic-tac-toe game",
  "a dashboard", "a todo app". When in doubt, choose "react". NEVER invent a framework the
  user didn't imply.
- "static": ONLY when the user explicitly asks for vanilla JS / plain HTML-CSS-JS / a static
  site / "no framework" / "no React".
- "nextjs": ONLY when the user explicitly asks for Next.js / Next / the app router / a
  multi-page app with routing.
You MAY ask ONE clarifying question about the framework ONLY if the request is sparse AND the
framework genuinely changes the build; otherwise default to "react" silently."""


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
    return f"""You are the INTAKE agent for an app generator that builds small web apps.
Decide whether the user's request is specific enough to build a good first version,
AND decide which framework to build it as.

User's original request: {prompt}

Answers gathered so far:
{history_text}

{FRAMEWORK_SELECTION_RULE}

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

Always include your current best `framework` choice ("react" | "static" | "nextjs") on EVERY
turn — both when asking a question and when ready.

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "ready": false,
  "question": "What kind of app do you want to build?",
  "options": ["A game", "A productivity tool", "A data dashboard", "A creative toy"],
  "brief": null,
  "framework": "react"
}}
OR, when ready:
{{
  "ready": true,
  "question": null,
  "options": [],
  "brief": "Build a tic-tac-toe game with a 3x3 board and a running score for X and O.",
  "framework": "react"
}}"""


# ── Per-framework file-shape guidance (planner + architect + coder share this) ──
# react reproduces the original wording verbatim so its behavior is unchanged.

_PLANNER_INTRO = {
    "react": 'a React app that will run in a CodeSandbox Sandpack\n"react" sandbox '
             "(CRA-style, entry file is /App.js)",
    "static": 'a STATIC HTML/CSS/JS site that will run in a CodeSandbox Sandpack\n"static" '
              "sandbox (entry file is /index.html — no build step)",
    "nextjs": 'a Next.js 14 (App Router) app that will run in a CodeSandbox Sandpack\n"nextjs" '
              "sandbox (entry route is /app/page.tsx)",
}

_PLANNER_RULES = {
    "react": """- Output a CLIENT-SIDE React SPA only (no server, no Node backend, no native deps).
- Entry component MUST be /App.js. Put extra components under /components/.
- ALWAYS include a /styles.css file in the plan (the app must be styled, not bare HTML).
- Use npm packages resolvable from a CDN — react, react-dom, and for data viz prefer
  `recharts`; date-fns for dates; etc. List them in techStack.""",
    "static": """- Output a STATIC site: plain HTML + CSS + VANILLA JS. NO React, NO JSX, NO build step,
  NO npm, NO package.json, NO bundler, NO ES-module imports.
- Entry MUST be /index.html — it links <link rel="stylesheet" href="styles.css"> in <head>
  and <script src="script.js" defer></script> before </body>.
- Plan exactly these files (add more .css/.js only if truly needed): /index.html, /styles.css,
  /script.js.
- All interactivity is vanilla DOM JS (document.querySelector, addEventListener, classList).
  The app MUST render by simply opening index.html — no server, no transpile.""",
    "nextjs": """- Output a SELF-CONTAINED Next.js 14 App Router app (no external DB/services; seed data in memory).
- Required files: /package.json (deps: next, react, react-dom), /app/layout.tsx (root layout that
  renders <html><body>{{children}}</body></html> and imports "./globals.css"), /app/page.tsx (the
  entry page), /app/globals.css. Add more routes as /app/<route>/page.tsx and components under
  /app/components/*.tsx as needed.
- Use idiomatic Next 14: Server Components by default; add "use client" ONLY to components that use
  hooks/handlers. NO pages-router APIs (no getServerSideProps/getStaticProps).
- Use TypeScript (.tsx/.ts). For data viz prefer `recharts`; list extra npm packages in techStack.""",
}

_PLANNER_TECHSTACK = {
    "react": '["React", "CSS"]',
    "static": '["HTML", "CSS", "JavaScript"]',
    "nextjs": '["Next.js", "React", "TypeScript", "CSS"]',
}

_PLANNER_FILES = {
    "react": """    {{"path": "/App.js", "purpose": "root component; imports ./styles.css"}},
    {{"path": "/styles.css", "purpose": "modern, polished styling for the whole app"}},
    {{"path": "/components/Board.js", "purpose": "..."}}""",
    "static": """    {{"path": "/index.html", "purpose": "entry; links styles.css and script.js"}},
    {{"path": "/styles.css", "purpose": "modern, polished styling for the whole app"}},
    {{"path": "/script.js", "purpose": "vanilla DOM logic and interactivity"}}""",
    "nextjs": """    {{"path": "/package.json", "purpose": "deps: next, react, react-dom"}},
    {{"path": "/app/layout.tsx", "purpose": "root layout; renders <html><body>; imports ./globals.css"}},
    {{"path": "/app/page.tsx", "purpose": "entry page"}},
    {{"path": "/app/globals.css", "purpose": "modern, polished global styling"}}""",
}

_ARCH_CONNECT = {
    "react": '/App.js imports the components AND imports\n"./styles.css". The /styles.css step '
             "must describe concrete, attractive styling (palette,\nlayout, button/input states) "
             "— not a placeholder.",
    "static": "/index.html links styles.css and script.js and contains the markup skeleton; "
              "script.js\nwires DOM behavior; the styles.css step must describe concrete, "
              "attractive styling (palette,\nlayout, button/input states) — not a placeholder.",
    "nextjs": '/app/layout.tsx imports "./globals.css" and renders <html><body>; /app/page.tsx is '
              "the entry;\ncomponents live under /app/components. The globals.css step must describe "
              "concrete, attractive\nstyling (palette, layout, button/input states) — not a placeholder.",
}

_ARCH_EXAMPLE = {
    "react": """    {{"filepath": "/styles.css", "task_description": "concrete modern styling: ..."}},
    {{"filepath": "/components/Board.js", "task_description": "detailed instructions"}},
    {{"filepath": "/App.js", "task_description": "imports ./styles.css and composes components"}}""",
    "static": """    {{"filepath": "/styles.css", "task_description": "concrete modern styling: ..."}},
    {{"filepath": "/index.html", "task_description": "markup skeleton; links styles.css + script.js"}},
    {{"filepath": "/script.js", "task_description": "vanilla DOM logic wired to the markup"}}""",
    "nextjs": """    {{"filepath": "/app/globals.css", "task_description": "concrete modern global styling: ..."}},
    {{"filepath": "/app/layout.tsx", "task_description": "root layout; imports ./globals.css"}},
    {{"filepath": "/app/page.tsx", "task_description": "entry page composing the components"}}""",
}


def planner_prompt(user_prompt: str, premium: bool = False, framework: str = "react") -> str:
    fw = framework if framework in _PLANNER_INTRO else "react"
    premium_block = f"\n{PREMIUM_GUIDELINES}\n" if premium else ""
    return f"""You are the PLANNER for {_PLANNER_INTRO[fw]}. Turn the request into a build plan.

User's request: {user_prompt}
{premium_block}

Rules:
{_PLANNER_RULES[fw]}
- AMBITION: design a genuinely CAPABLE, production-feeling first version — NOT a toy. Decompose
  into several real components/sections (5-9 files is normal for a rich app). For a "dashboard", plan
  MULTIPLE metric cards, 2+ charts (different types), a data table/list, and filters/controls;
  if the user said "real-time", plan simulated live data that updates on an interval. Cover the
  core feature deeply with sensible realistic seed data — a reviewer should think "this is a
  real app", not "this is a demo stub".

{DESIGN_GUIDELINES}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "name": "App Name",
  "description": "one-line description",
  "techStack": {_PLANNER_TECHSTACK[fw]},
  "features": ["feature 1", "feature 2"],
  "files": [
{_PLANNER_FILES[fw]}
  ]
}}"""


def architect_prompt(plan_json: str, premium: bool = False, framework: str = "react") -> str:
    fw = framework if framework in _ARCH_CONNECT else "react"
    premium_block = f"\n{PREMIUM_GUIDELINES}\n" if premium else ""
    return f"""You are the ARCHITECT. Break the plan into ordered, self-contained
implementation steps — one per file.{premium_block}

For each step specify exactly what to implement (component names, props, state, handlers)
and how files connect (imports/exports). {_ARCH_CONNECT[fw]} Order dependencies first. Each step
must be self-contained.

{DESIGN_GUIDELINES}

Project plan (JSON):
{plan_json}

Respond with ONLY valid JSON — no prose, no markdown, no code fences:
{{
  "implementation_steps": [
{_ARCH_EXAMPLE[fw]}
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


_STATIC_SYSTEM_PROMPT = (
    "You are the CODER. You implement ALL files of a STATIC HTML/CSS/JS site in ONE response, "
    "for a CodeSandbox Sandpack 'static' sandbox (entry /index.html). NO React, NO JSX, NO npm, "
    "NO package.json, NO bundler, NO ES-module imports — plain HTML5, CSS, and VANILLA browser JS. "
    "/index.html links <link rel=\"stylesheet\" href=\"styles.css\"> in <head> and "
    "<script src=\"script.js\" defer></script> before </body>. "
    "Wire all interactivity with vanilla DOM JS (document.querySelector, addEventListener, "
    "classList, textContent) — the page MUST render and work by simply opening index.html. "
    "CORRECTNESS: guard every querySelector result before use; attach listeners after DOMContentLoaded "
    "(or use defer); no undefined globals; no console errors. "
    "PRODUCE VISUALLY POLISHED UIs: use CSS variables for color tokens, a gradient accent on the "
    "header/primary buttons, system font stack, rem-based type scale, comfortable spacing, rounded "
    "corners (12-16px), soft box-shadows, a responsive container, smooth 0.2s transitions, hover/active "
    "states, focus-visible outlines, and a fadeInUp keyframe. Write real, complete, modern CSS."
)

_NEXTJS_SYSTEM_PROMPT = (
    "You are the CODER. You implement ALL files of a Next.js 14 App Router app in ONE response, "
    "for a CodeSandbox Sandpack 'nextjs' sandbox. Entry route is /app/page.tsx; /app/layout.tsx is "
    "the root layout that renders <html><body>{children}</body></html> and imports \"./globals.css\". "
    "Use TypeScript (.tsx/.ts) and idiomatic Next 14: Server Components by default, with the "
    "\"use client\" directive at the TOP of any file that uses hooks (useState/useEffect) or event "
    "handlers. NO pages-router APIs. Keep it SELF-CONTAINED (in-memory/seed data, no external services). "
    "/package.json MUST declare next, react, and react-dom. Import components by relative path; EVERY "
    "imported file MUST be emitted in this response — no orphan imports. Only CDN-resolvable npm packages. "
    "CORRECTNESS: never render an object/array directly as a JSX child; initialize state before use; "
    "guard .map over possibly-undefined data; stable list keys; the app must build and run with NO errors. "
    "PRODUCE VISUALLY POLISHED UIs: CSS variables for color tokens, a gradient accent on the header/primary "
    "buttons, system font stack, rem-based type scale, rounded corners (12-16px), soft box-shadows, smooth "
    "0.2s transitions, hover/active states, focus-visible outlines. Write real, complete, modern CSS in globals.css."
)

_CODER_SYSTEM_PROMPTS = {
    "react": CODER_SYSTEM_PROMPT,
    "static": _STATIC_SYSTEM_PROMPT,
    "nextjs": _NEXTJS_SYSTEM_PROMPT,
}


def coder_system_prompt(framework: str = "react") -> str:
    """Pick the CODER system prompt for the framework (defaults to react)."""
    return _CODER_SYSTEM_PROMPTS.get(framework, CODER_SYSTEM_PROMPT)


# Per-framework coder body: completeness rules + the file-format example header.
_CODER_RULES = {
    "react": """FUNCTIONAL COMPLETENESS RULES (non-negotiable):
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
  use the palette tokens; add recharts to /package.json dependencies.""",
    "static": """FUNCTIONAL COMPLETENESS RULES (non-negotiable):
- /index.html MUST contain the FULL markup skeleton; /script.js MUST wire the ENTIRE feature
  with vanilla DOM JS — not a shell. NO React, NO JSX, NO imports, NO package.json.
- Every element script.js touches must exist in index.html; guard every querySelector.
- Build/initialize the UI on DOMContentLoaded (or rely on `defer`).

BUILD A CAPABLE, POLISHED APP — NOT A STUB:
- Implement the FULL feature set with real interactivity driven by event listeners and state held
  in plain JS variables/objects; re-render the relevant DOM on change. A reviewer should think
  "this is a real app".
- GAMES/grids: build the grid in HTML (or generate cells in JS), style sized bordered clickable
  cells via CSS Grid, and wire real win/score logic to clicks.
- For charts WITHOUT a library, draw with <canvas> or styled divs; data lives in JS arrays.
- "REAL-TIME": use setInterval to update state + DOM every 1-2s; clearInterval when appropriate.""",
    "nextjs": """FUNCTIONAL COMPLETENESS RULES (non-negotiable):
- /app/page.tsx MUST render the ENTIRE feature UI; /app/layout.tsx imports "./globals.css" and
  renders <html><body>{children}</body></html>.
- EVERY component imported by ANY file MUST be defined in this response — no orphan imports.
- Put "use client" at the TOP of any file using hooks or event handlers. Server Components otherwise.
- ONE source of truth for shared state: lift it into the page (a client component) and pass props down.

BUILD A CAPABLE, PRODUCTION-FEELING APP — NOT A STUB:
- Implement the FULL feature set with real interactivity — a reviewer should think "this is a real app".
- DASHBOARDS: MULTIPLE metric/stat cards (value, label, delta), 2+ charts of DIFFERENT types via
  `recharts` (each in <ResponsiveContainer>), AND a data table/list, plus working filters. Seed with
  rich realistic data (15-30+ points). recharts needs "use client"; add it to /package.json.
- Multi-page: add routes as /app/<route>/page.tsx and link with next/link.
- "REAL-TIME": a client component with useEffect+setInterval updating state every 1-2s; cleanup on unmount.""",
}

_CODER_FORMAT_EXAMPLE = {
    "react": "=== FILE: /styles.css ===\n(full file body here)\n=== FILE: /App.js ===\n(full file body here)",
    "static": "=== FILE: /index.html ===\n(full file body here)\n=== FILE: /styles.css ===\n(full file body here)\n=== FILE: /script.js ===\n(full file body here)",
    "nextjs": "=== FILE: /app/globals.css ===\n(full file body here)\n=== FILE: /app/layout.tsx ===\n(full file body here)\n=== FILE: /app/page.tsx ===\n(full file body here)",
}


def coder_prompt(task_steps: list[dict], plan_json: str, premium: bool = False,
                 framework: str = "react") -> str:
    """Build the single-call prompt that generates ALL app files at once."""
    fw = framework if framework in _CODER_RULES else "react"
    steps_text = "\n".join(
        f"  {i+1}. {s['filepath']}: {s['task_description']}"
        for i, s in enumerate(task_steps)
    )
    file_list = ", ".join(s["filepath"] for s in task_steps)
    premium_block = f"\n{PREMIUM_GUIDELINES}\n" if premium else ""
    return f"""Project plan:
{plan_json}

Implementation steps (for ALL files you must produce):
{steps_text}

{DESIGN_GUIDELINES}
{premium_block}

{_CODER_RULES[fw]}

Output ALL {len(task_steps)} files in this EXACT format — no prose before/after, no markdown fences around the file delimiter lines:

{_CODER_FORMAT_EXAMPLE[fw]}

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


def uxmaster_prompt(files: dict[str, str], instruction: str, image_provided: bool = True) -> str:
    """Build the single-call UX MASTER prompt.

    A vision review: the model sees a SCREENSHOT of the running app (sent alongside this
    prompt as an image) plus the current code, critiques the ACTUAL rendered UI, and returns
    the COMPLETE improved file set. Output adds a `=== VERIFY ===` boolean block (does UX
    Master want a fresh screenshot to confirm the change landed?) between REPLY and the files.
    """
    current_files_text = "\n".join(
        f"=== FILE: {path} ===\n{content}" for path, content in files.items()
    )
    file_list = ", ".join(files.keys())
    screenshot_line = (
        "A SCREENSHOT of the running app is attached to this message — review what it ACTUALLY renders."
        if image_provided
        else "No screenshot was provided — review the code and infer the rendered UI."
    )
    user_focus = instruction.strip() if instruction and instruction.strip() else (
        "Do a full design pass and raise the visual quality."
    )
    return f"""You are UX MASTER, a senior product designer reviewing a SCREENSHOT of the running app plus its code.
{screenshot_line}

Critique the ACTUAL rendered UI — visual hierarchy, spacing/rhythm, contrast/legibility,
alignment, polish, responsiveness cues — and IMPROVE the code accordingly (follow DESIGN_GUIDELINES).
Don't just restyle blindly: tie each change to something you can see in the screenshot.

User's focus for this pass:
{user_focus}

Current app files:
{current_files_text}

{DESIGN_GUIDELINES}

RULES:
- Keep it a working CodeSandbox Sandpack 'react' app (entry /App.js, /App.js imports "./styles.css").
- Apply real, substantial design improvements — not cosmetic tweaks. Keep ALL behavior intact;
  no missing imports, no broken references. The app must mount with NO console errors.
- Emit EVERY file (modified or unchanged) so the full file set is complete.

Output your response in this EXACT format — FIRST a REPLY block, THEN a VERIFY block, THEN ALL files.
No prose before/after, no markdown fences:

=== REPLY ===
A first-person, conversational message AS "UX MASTER": what you saw in the screenshot, what you
changed, and WHY. Talk like a design partner, not a changelog.
=== VERIFY ===
true
(this block contains EXACTLY `true` or `false` — `true` if you want the user to send a NEW
screenshot so you can verify your change landed; `false` if you're confident. YOU decide.)
=== FILE: /styles.css ===
(full file body here)
=== FILE: /App.js ===
(full file body here)

Files to emit (all of them, in dependency order): {file_list}

Use EXACTLY the delimiter format above (one REPLY block, one VERIFY block, then each file).
No other text outside the delimiters."""


def vibe_prompt(files: dict[str, str], instruction: str, premium: bool = False) -> str:
    """Build the single-call VibeEngineer prompt.

    Embeds current files (=== FILE: === blocks) + instruction and asks for
    the COMPLETE updated file set in the same delimited format.

    ponytail: premium=True appends PREMIUM_GUIDELINES so SUPER_ADMIN edits are held to the
    same production-grade bar as premium generation. oncall_prompt keeps the default (False).
    """
    current_files_text = "\n".join(
        f"=== FILE: {path} ===\n{content}" for path, content in files.items()
    )
    file_list = ", ".join(files.keys())
    premium_block = f"\n{PREMIUM_GUIDELINES}\n" if premium else ""
    return f"""You are the VIBE ENGINEER for a React app running in a CodeSandbox Sandpack 'react' sandbox.

The user wants to modify the existing app with the following instruction:
{instruction}

Current app files:
{current_files_text}

{DESIGN_GUIDELINES}
{premium_block}

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

Output your response in this EXACT format — FIRST a single REPLY block, THEN ALL files.
No prose before/after, no markdown fences:

=== REPLY ===
A SHORT (1-3 sentence) first-person, conversational message AS "the VibeEngineer", telling the
user what you just changed and (optionally) offering an obvious next step. Talk like a teammate,
not a changelog. Example: "Done — switched the palette to a calm dark teal and added a hover lift
to the cards. Want me to animate the chart next?"
=== FILE: /styles.css ===
(full file body here)
=== FILE: /App.js ===
(full file body here)

Files to emit (all of them, in dependency order): {file_list}

Use EXACTLY the delimiter format above (one REPLY block, then each file). No other text outside the delimiters."""
