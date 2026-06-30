import json
from agent import scaffold


def test_normalize_adds_leading_slash_and_package_json():
    files = {"App.js": "export default () => null"}
    out = scaffold.normalize_files(files)
    assert "/App.js" in out
    assert "/package.json" in out
    pkg = json.loads(out["/package.json"])
    assert "react" in pkg["dependencies"]


def test_is_sandpack_shaped():
    assert scaffold.is_sandpack_shaped({"/App.js": "x", "/package.json": "{}"})
    assert not scaffold.is_sandpack_shaped({"/index.html": "x"})


def test_default_package_json_merges_extra_deps():
    pkg = json.loads(scaffold.default_package_json("demo", {"lodash": "^4.17.21"}))
    assert pkg["dependencies"]["lodash"] == "^4.17.21"
    assert "react" in pkg["dependencies"]


def test_ensure_dependencies_adds_imported_npm_packages():
    from agent.scaffold import normalize_files
    import json as _json
    files = {
        "/App.js": (
            'import { LineChart } from "recharts";\n'
            'import Board from "./components/Board";\n'
            'export default function App() { return null }'
        ),
        "/package.json": '{"name":"x","dependencies":{"react":"^18.2.0","react-dom":"^18.2.0"}}',
    }
    deps = _json.loads(normalize_files(files)["/package.json"])["dependencies"]
    assert "recharts" in deps          # bare npm import declared
    assert "react" in deps             # base kept
    assert "./components/Board" not in deps  # relative import never added


# ── to_vite_project: Sandpack → deployable Vite + React repo ────────────────────

_SANDPACK = {
    "/App.js": (
        'import "./styles.css";\n'
        'import Chart from "./components/Chart";\n'
        'import { LineChart } from "recharts";\n'
        "export default function App() { return <Chart/>; }\n"
    ),
    "/components/Chart.js": "export default function Chart(){ return <div>chart</div>; }\n",
    "/styles.css": "body { margin: 0; }\n",
    "/package.json": (
        '{"name":"x","dependencies":{"react":"^18.2.0","react-dom":"^18.2.0","recharts":"^2.15.0"}}'
    ),
}


def test_to_vite_project_core_files():
    out = scaffold.to_vite_project(_SANDPACK, "My Cool App")
    # required Vite scaffolding
    assert "index.html" in out
    assert 'id="root"' in out["index.html"]
    assert '/src/main.jsx' in out["index.html"]
    assert "src/main.jsx" in out
    assert "ReactDOM.createRoot" in out["src/main.jsx"]
    assert "import App from './App'" in out["src/main.jsx"]
    assert "import './styles.css'" in out["src/main.jsx"]
    # App + components moved under src/, .js → .jsx
    assert "src/App.jsx" in out
    assert "src/components/Chart.jsx" in out
    assert "src/styles.css" in out
    assert "vite.config.js" in out
    assert "@vitejs/plugin-react" in out["vite.config.js"]
    assert "README.md" in out


def test_to_vite_project_package_json():
    out = scaffold.to_vite_project(_SANDPACK, "My Cool App")
    pkg = json.loads(out["package.json"])
    assert pkg["type"] == "module"
    assert pkg["scripts"]["build"] == "vite build"
    assert pkg["scripts"]["dev"] == "vite"
    # app dependency carried over
    assert pkg["dependencies"]["recharts"] == "^2.15.0"
    assert "react" in pkg["dependencies"]
    assert "react-dom" in pkg["dependencies"]
    # vite toolchain in devDependencies
    assert "vite" in pkg["devDependencies"]
    assert "@vitejs/plugin-react" in pkg["devDependencies"]
    # name slugified
    assert pkg["name"] == "my-cool-app"


def test_slugify():
    assert scaffold.slugify("My Cool App!!") == "my-cool-app"
    assert scaffold.slugify("") == "app"


# ── framework helpers + framework-aware normalize_files ──────────────────────


def test_coerce_framework_valid_and_invalid():
    assert scaffold.coerce_framework("static") == "static"
    assert scaffold.coerce_framework("NextJS") == "nextjs"
    assert scaffold.coerce_framework("vue") == "react"      # unknown → default
    assert scaffold.coerce_framework(None) == "react"
    assert scaffold.coerce_framework("") == "react"


def test_detect_framework():
    assert scaffold.detect_framework({"/app/page.tsx": "x", "/package.json": "{}"}) == "nextjs"
    assert scaffold.detect_framework({"/index.html": "x", "/styles.css": "y", "/script.js": "z"}) == "static"
    assert scaffold.detect_framework({"/App.js": "x", "/package.json": "{}"}) == "react"


def test_normalize_static_no_react_or_package_json():
    """static: never inject /App.js or /package.json; ensure /index.html exists."""
    out = scaffold.normalize_files({"index.html": "<h1>hi</h1>", "script.js": "//"}, "static")
    assert "/index.html" in out
    assert "/App.js" not in out
    assert "/package.json" not in out


def test_normalize_static_injects_index_when_missing():
    out = scaffold.normalize_files({"/styles.css": "body{}"}, "static")
    assert "/index.html" in out
    assert "script.js" in out["/index.html"]  # default entry links the vanilla script
    assert "/package.json" not in out


def test_normalize_nextjs_ensures_entry_and_next_dep():
    files = {"/app/page.tsx": 'import Foo from "./foo";\nexport default function Page(){return null}'}
    out = scaffold.normalize_files(files, "nextjs")
    assert "/app/page.tsx" in out
    assert "/App.js" not in out
    deps = json.loads(out["/package.json"])["dependencies"]
    assert deps.get("next")
    assert "react" in deps and "react-dom" in deps


def test_normalize_nextjs_injects_page_when_missing():
    out = scaffold.normalize_files({"/app/globals.css": "body{}"}, "nextjs")
    assert "/app/page.tsx" in out
    assert "next" in json.loads(out["/package.json"])["dependencies"]


def test_normalize_react_unchanged_default():
    """react (default arg) keeps injecting /App.js + /package.json."""
    out = scaffold.normalize_files({"App.js": "export default () => null"})
    assert "/App.js" in out
    assert "react" in json.loads(out["/package.json"])["dependencies"]


# ── parse_uxmaster_response ──────────────────────────────────────────────────

from agent.llm import strip_code_fences


def test_parse_uxmaster_extracts_reply_verify_and_files():
    raw = (
        "=== REPLY ===\n"
        "I saw cramped spacing and low contrast — bumped the padding and darkened text.\n"
        "=== VERIFY ===\n"
        "true\n"
        "=== FILE: /App.js ===\n"
        "export default function App(){return <h1>Hi</h1>;}\n"
        "=== FILE: /styles.css ===\n"
        "body { margin: 0; }\n"
    )
    reply, needs_verification, files = scaffold.parse_uxmaster_response(raw, strip_code_fences)
    assert reply.startswith("I saw cramped spacing")
    assert "VERIFY" not in reply  # verify block trimmed out of the reply
    assert needs_verification is True
    assert set(files.keys()) == {"/App.js", "/styles.css"}


def test_parse_uxmaster_verify_false():
    raw = (
        "=== REPLY ===\nLooks solid now.\n"
        "=== VERIFY ===\nfalse\n"
        "=== FILE: /App.js ===\nconst x=1;\n"
    )
    reply, needs_verification, files = scaffold.parse_uxmaster_response(raw, strip_code_fences)
    assert needs_verification is False
    assert reply == "Looks solid now."
    assert "/App.js" in files


def test_parse_uxmaster_verify_defaults_false_when_absent():
    raw = (
        "=== REPLY ===\nTweaked it.\n"
        "=== FILE: /App.js ===\nconst x=1;\n"
    )
    reply, needs_verification, files = scaffold.parse_uxmaster_response(raw, strip_code_fences)
    assert needs_verification is False
    assert reply == "Tweaked it."
    assert "/App.js" in files
