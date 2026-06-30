import json
import re

SANDPACK_TEMPLATE = "react"

# ponytail: the three app shapes the generator can produce. "react" is the default and
# keeps all historical behavior; "static" = plain HTML/CSS/JS; "nextjs" = App Router.
FRAMEWORKS: tuple[str, ...] = ("react", "static", "nextjs")


def coerce_framework(value) -> str:
    """Validate a framework string at a boundary; unknown/invalid → 'react' (the default)."""
    v = value.strip().lower() if isinstance(value, str) else ""
    return v if v in FRAMEWORKS else "react"


def detect_framework(files: dict[str, str]) -> str:
    """Infer the framework of an existing file set (for enhance/oncall/uxmaster which only
    receive files). Next.js wins on app/ or pages/ routes; static on a bundler-free index.html;
    everything else is react (the default)."""
    norm = {(k if k.startswith("/") else "/" + k) for k in files}
    if any(k.startswith(("/app/", "/pages/")) for k in norm) or "/next.config.js" in norm:
        return "nextjs"
    has_index = "/index.html" in norm
    has_react_entry = any(k in norm for k in ("/App.js", "/App.jsx"))
    has_pkg = "/package.json" in norm
    if has_index and not has_react_entry and not has_pkg:
        return "static"
    return "react"

_FILE_HEADER_RE = re.compile(r"^=== FILE: (.+?) ===$", re.MULTILINE)
_REPLY_HEADER_RE = re.compile(r"^=== REPLY ===\s*$", re.MULTILINE)
_VERIFY_HEADER_RE = re.compile(r"^=== VERIFY ===\s*$", re.MULTILINE)


def parse_multi_file_response(raw: str, strip_fences_fn) -> dict[str, str]:
    """Parse a delimited multi-file LLM response into a filepath→content dict.

    Expected format:
        === FILE: /App.js ===
        <file body>
        === FILE: /styles.css ===
        <file body>
    """
    matches = list(_FILE_HEADER_RE.finditer(raw))
    if not matches:
        raise ValueError("No file headers found in coder response (expected '=== FILE: /path ===').")
    files: dict[str, str] = {}
    for i, match in enumerate(matches):
        filepath = match.group(1).strip()
        start = match.end() + 1  # skip the newline after the header
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end]
        files[filepath] = strip_fences_fn(body)
    return files


def parse_reply_and_files(raw: str, strip_fences_fn) -> tuple[str, dict[str, str]]:
    """Split a VibeEngineer response into (reply, files).

    The response leads with an optional `=== REPLY ===` block (a short conversational
    message) followed by the usual `=== FILE: /path ===` blocks. The reply is the text
    between the REPLY header and the first FILE header. Files are parsed exactly as before
    (parse_multi_file_response ignores the REPLY header — it only matches FILE: headers),
    so callers that don't need the reply keep working unchanged.
    """
    reply = ""
    reply_match = _REPLY_HEADER_RE.search(raw)
    if reply_match:
        file_match = _FILE_HEADER_RE.search(raw, reply_match.end())
        end = file_match.start() if file_match else len(raw)
        reply = raw[reply_match.end():end].strip()
    files = parse_multi_file_response(raw, strip_fences_fn)
    return reply, files


def parse_uxmaster_response(
    raw: str, strip_fences_fn
) -> tuple[str, bool, dict[str, str]]:
    """Split a UX MASTER response into (reply, needs_verification, files).

    Same shape as parse_reply_and_files but with an extra `=== VERIFY ===` block (containing
    `true`/`false`) between the REPLY block and the first FILE block. Reuses
    parse_reply_and_files for reply + files, then narrows the reply to end at the VERIFY header
    and reads the boolean. needs_verification defaults False when the VERIFY block is absent.
    """
    reply, files = parse_reply_and_files(raw, strip_fences_fn)
    needs_verification = False
    verify_match = _VERIFY_HEADER_RE.search(raw)
    if verify_match:
        reply_match = _REPLY_HEADER_RE.search(raw)
        if reply_match:
            # parse_reply_and_files swept the VERIFY block into reply — trim it back out.
            reply = raw[reply_match.end():verify_match.start()].strip()
        file_match = _FILE_HEADER_RE.search(raw, verify_match.end())
        end = file_match.start() if file_match else len(raw)
        verify_text = raw[verify_match.end():end].strip().lower()
        needs_verification = verify_text.startswith("true")
    return reply, needs_verification, files


BASE_DEPENDENCIES: dict[str, str] = {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
}

# Known-good versions for libs the coder commonly reaches for; anything else → "latest".
_KNOWN_VERSIONS: dict[str, str] = {
    "recharts": "^2.15.0",
    "date-fns": "^3.6.0",
    "lucide-react": "^0.460.0",
    "framer-motion": "^11.11.0",
    "clsx": "^2.1.1",
    "uuid": "^9.0.1",
    "nanoid": "^5.0.0",
    "zustand": "^4.5.0",
}
# import sources that are NOT npm packages to install.
_NON_PKG_PREFIXES = (".", "/")
_BUILTIN_PKGS = {"react", "react-dom"}

_IMPORT_RE = re.compile(r"""(?:import\s[^'"]*?from\s|import\s|from\s)['"]([^'"]+)['"]""")


def _package_name(source: str) -> str | None:
    """Resolve an import source to its npm package name (handles scopes + subpaths)."""
    if source.startswith(_NON_PKG_PREFIXES):
        return None
    parts = source.split("/")
    name = "/".join(parts[:2]) if source.startswith("@") else parts[0]
    return name or None


def ensure_dependencies(files: dict[str, str]) -> dict[str, str]:
    """Scan all JS/TS files for bare npm imports and add any missing ones to /package.json.

    ponytail: the coder sometimes imports a lib (e.g. recharts) without listing it in
    package.json → Sandpack can't resolve it. This guarantees every imported package is
    declared so the preview always boots.
    """
    pkg_key = "/package.json" if "/package.json" in files else "package.json"
    if pkg_key not in files:
        return files
    try:
        pkg = json.loads(files[pkg_key])
    except (json.JSONDecodeError, TypeError):
        return files
    deps: dict[str, str] = pkg.get("dependencies", {}) or {}

    imported: set[str] = set()
    for path, content in files.items():
        if not path.endswith((".js", ".jsx", ".ts", ".tsx")) or not isinstance(content, str):
            continue
        for src in _IMPORT_RE.findall(content):
            name = _package_name(src)
            if name and name not in _BUILTIN_PKGS:
                imported.add(name)

    changed = False
    for name in imported:
        if name not in deps:
            deps[name] = _KNOWN_VERSIONS.get(name, "latest")
            changed = True
    if not changed:
        return files

    pkg["dependencies"] = deps
    out = dict(files)
    out[pkg_key] = json.dumps(pkg, indent=2)
    return out


def default_package_json(name: str, extra_deps: dict[str, str] | None = None) -> str:
    deps = dict(BASE_DEPENDENCIES)
    if extra_deps:
        deps.update(extra_deps)
    pkg = {
        "name": name or "sandbox-app",
        "version": "1.0.0",
        "main": "/index.js",
        "dependencies": deps,
    }
    return json.dumps(pkg, indent=2)


NEXT_BASE_DEPENDENCIES: dict[str, str] = {
    "next": "^14.2.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
}

_DEFAULT_STATIC_INDEX = (
    "<!doctype html>\n"
    '<html lang="en">\n'
    "  <head>\n"
    '    <meta charset="UTF-8" />\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
    "    <title>App</title>\n"
    '    <link rel="stylesheet" href="styles.css" />\n'
    "  </head>\n"
    "  <body>\n"
    "    <h1>Empty app</h1>\n"
    '    <script src="script.js" defer></script>\n'
    "  </body>\n"
    "</html>\n"
)

_DEFAULT_NEXT_PAGE = (
    "export default function Page() {\n"
    "  return (\n"
    "    <main>\n"
    "      <h1>Empty app</h1>\n"
    "    </main>\n"
    "  );\n"
    "}\n"
)

_NEXT_ENTRY_KEYS = ("/app/page.tsx", "/app/page.jsx", "/pages/index.tsx", "/pages/index.js")


def _ensure_next_package_json(files: dict[str, str]) -> dict[str, str]:
    """Guarantee /package.json exists and declares next/react/react-dom (Sandpack nextjs)."""
    key = "/package.json"
    try:
        pkg = json.loads(files[key]) if key in files else {}
    except (json.JSONDecodeError, TypeError):
        pkg = {}
    if not isinstance(pkg, dict):
        pkg = {}
    pkg.setdefault("name", "sandbox-app")
    pkg.setdefault("version", "1.0.0")
    deps = pkg.get("dependencies") or {}
    for name, version in NEXT_BASE_DEPENDENCIES.items():
        deps.setdefault(name, version)
    pkg["dependencies"] = deps
    out = dict(files)
    out[key] = json.dumps(pkg, indent=2)
    return out


def normalize_files(files: dict[str, str], framework: str = "react") -> dict[str, str]:
    """Normalize an LLM file set to a bootable Sandpack project for the given framework.

    Default 'react' keeps every historical caller working unchanged.
    """
    framework = coerce_framework(framework)
    out: dict[str, str] = {}
    for path, content in files.items():
        key = path if path.startswith("/") else "/" + path
        out[key] = content

    if framework == "static":
        # plain HTML/CSS/JS — NO React entry, NO package.json, NO npm dependency scan.
        if "/index.html" not in out:
            out["/index.html"] = _DEFAULT_STATIC_INDEX
        return out

    if framework == "nextjs":
        # App Router — ensure an entry page + next/react/react-dom deps, then declare extras.
        if not any(k in out for k in _NEXT_ENTRY_KEYS):
            out["/app/page.tsx"] = _DEFAULT_NEXT_PAGE
        out = _ensure_next_package_json(out)
        return ensure_dependencies(out)

    # react (default) — unchanged behavior.
    if "/App.js" not in out and "/App.jsx" not in out:
        out["/App.js"] = (
            "export default function App() {\n"
            "  return <h1>Empty app</h1>;\n"
            "}\n"
        )
    if "/package.json" not in out:
        out["/package.json"] = default_package_json("sandbox-app")
    return ensure_dependencies(out)  # auto-declare any imported npm packages


def is_sandpack_shaped(files: dict[str, str]) -> bool:
    has_entry = any(k in files for k in ("/App.js", "/App.jsx", "App.js", "App.jsx"))
    has_pkg = any(k in files for k in ("/package.json", "package.json"))
    return has_entry and has_pkg


_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Vite toolchain pins (devDeps) for the generated deployable repo.
_VITE_DEV_DEPENDENCIES: dict[str, str] = {
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.0",
}


def slugify(text: str) -> str:
    """Lowercase, hyphenate; safe for repo/package names. Falls back to 'app'."""
    slug = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return slug or "app"


def to_vite_project(files: dict[str, str], name: str) -> dict[str, str]:
    """Transform a Sandpack-shaped file set into a deployable Vite + React repo.

    Sandpack files (entry /App.js, /components/*, /styles.css, /package.json) are NOT
    directly deployable. This produces a real Vite project Vercel can `vite build`:
      index.html → loads /src/main.jsx; src/main.jsx mounts <App/> into #root;
      /App.js → src/App.jsx; /components/* → src/components/*; /styles.css → src/styles.css;
      a Vite package.json (type:module, dev/build/preview scripts, app deps + react +
      vite devDeps); vite.config.js; README.md.

    ponytail: source .js → .jsx (Vite/esbuild needs .jsx for JSX) — coder emits EXTENSIONLESS
    relative imports (import Board from './components/Board'), so the rename keeps them valid.
    """
    out: dict[str, str] = {}
    app_deps: dict[str, str] = {}
    styles_present = False

    for path, content in files.items():
        norm = path.lstrip("/")
        if norm == "package.json":
            try:
                app_deps = (json.loads(content) or {}).get("dependencies", {}) or {}
            except (json.JSONDecodeError, TypeError):
                app_deps = {}
            continue
        if norm in ("index.js", "index.jsx"):
            continue  # Sandpack entry shim — Vite uses src/main.jsx instead
        if norm in ("App.js", "App.jsx"):
            out["src/App.jsx"] = content
            continue
        if norm == "styles.css":
            out["src/styles.css"] = content
            styles_present = True
            continue
        target = norm[:-3] + ".jsx" if norm.endswith(".js") else norm
        out["src/" + target] = content

    if "src/App.jsx" not in out:
        out["src/App.jsx"] = "export default function App() {\n  return <h1>Empty app</h1>;\n}\n"

    deps = dict(app_deps)
    deps.pop("react", None)
    deps.pop("react-dom", None)
    deps = {**BASE_DEPENDENCIES, **deps}  # canonical react/react-dom first, then app deps

    pkg = {
        "name": slugify(name),
        "private": True,
        "version": "0.0.0",
        "type": "module",
        "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "dependencies": deps,
        "devDependencies": dict(_VITE_DEV_DEPENDENCIES),
    }
    out["package.json"] = json.dumps(pkg, indent=2)

    out["vite.config.js"] = (
        "import { defineConfig } from 'vite';\n"
        "import react from '@vitejs/plugin-react';\n\n"
        "export default defineConfig({\n  plugins: [react()],\n});\n"
    )

    title = name or "App"
    out["index.html"] = (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="UTF-8" />\n'
        '    <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"    <title>{title}</title>\n"
        "  </head>\n"
        "  <body>\n"
        '    <div id="root"></div>\n'
        '    <script type="module" src="/src/main.jsx"></script>\n'
        "  </body>\n"
        "</html>\n"
    )

    style_import = "import './styles.css';\n" if styles_present else ""
    out["src/main.jsx"] = (
        "import React from 'react';\n"
        "import ReactDOM from 'react-dom/client';\n"
        "import App from './App';\n"
        f"{style_import}"
        "\n"
        "ReactDOM.createRoot(document.getElementById('root')).render(\n"
        "  <React.StrictMode>\n"
        "    <App />\n"
        "  </React.StrictMode>\n"
        ");\n"
    )

    out["README.md"] = (
        f"# {title}\n\n"
        "Generated by AppSmith / CodyBuddy Studio. A Vite + React app.\n\n"
        "## Develop\n\n"
        "```bash\nnpm install\nnpm run dev\n```\n\n"
        "## Build\n\n"
        "```bash\nnpm run build\n```\n\n"
        "Deploy on Vercel (framework preset: Vite) — `npm run build`, output `dist/`.\n"
    )
    return out
