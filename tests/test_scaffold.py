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
