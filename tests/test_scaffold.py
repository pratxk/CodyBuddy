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
