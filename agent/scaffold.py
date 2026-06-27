import json

SANDPACK_TEMPLATE = "react"

BASE_DEPENDENCIES: dict[str, str] = {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
}


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


def normalize_files(files: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path, content in files.items():
        key = path if path.startswith("/") else "/" + path
        out[key] = content
    if "/App.js" not in out and "/App.jsx" not in out:
        out["/App.js"] = (
            "export default function App() {\n"
            "  return <h1>Empty app</h1>;\n"
            "}\n"
        )
    if "/package.json" not in out:
        out["/package.json"] = default_package_json("sandbox-app")
    return out


def is_sandpack_shaped(files: dict[str, str]) -> bool:
    has_entry = any(k in files for k in ("/App.js", "/App.jsx", "App.js", "App.jsx"))
    has_pkg = any(k in files for k in ("/package.json", "package.json"))
    return has_entry and has_pkg
