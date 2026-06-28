import json
import re

SANDPACK_TEMPLATE = "react"

_FILE_HEADER_RE = re.compile(r"^=== FILE: (.+?) ===$", re.MULTILINE)


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
    return ensure_dependencies(out)  # auto-declare any imported npm packages


def is_sandpack_shaped(files: dict[str, str]) -> bool:
    has_entry = any(k in files for k in ("/App.js", "/App.jsx", "App.js", "App.jsx"))
    has_pkg = any(k in files for k in ("/package.json", "package.json"))
    return has_entry and has_pkg
