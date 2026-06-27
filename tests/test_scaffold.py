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
