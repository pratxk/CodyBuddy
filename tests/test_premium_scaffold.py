import json
import re

from agent import premium_scaffold as ps
from agent.scaffold import ensure_dependencies, is_sandpack_shaped

# The exact §2.1 file list the scaffold must ship.
REQUIRED_PATHS = (
    "/styles.css",
    "/ui/AppShell.js",
    "/ui/Card.js",
    "/ui/ChartCard.js",
    "/ui/KPIStat.js",
    "/ui/DataTable.js",
    "/ui/Badge.js",
    "/ui/Button.js",
    "/ui/Sidebar.js",
    "/ui/Topbar.js",
    "/ui/Tabs.js",
    "/ui/Toast.js",
    "/ui/ProgressBar.js",
    "/ui/Modal.js",
    "/ui/icon.js",
    "/ui/index.js",
    "/lib/format.js",
)

PRIMITIVE_NAMES = (
    "AppShell",
    "Card",
    "ChartCard",
    "KPIStat",
    "DataTable",
    "Badge",
    "Button",
    "Sidebar",
    "Topbar",
    "Tabs",
    "Toast",
    "ProgressBar",
    "Modal",
)

# Hex color literal used in a CSS/JS style position, e.g. #fff / #F97316 / #0f172a.
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def test_scaffold_contains_every_required_path():
    for path in REQUIRED_PATHS:
        assert path in ps.PREMIUM_SCAFFOLD_FILES, f"missing {path}"


def test_all_paths_slash_prefixed_and_non_empty():
    for path, source in ps.PREMIUM_SCAFFOLD_FILES.items():
        assert path.startswith("/"), f"{path} not /-prefixed"
        assert isinstance(source, str) and source.strip(), f"{path} empty"


def test_barrel_reexports_every_primitive():
    barrel = ps.PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    for name in PRIMITIVE_NAMES:
        assert re.search(rf"\b{name}\b", barrel), f"{name} not re-exported in barrel"


def test_styles_defines_required_tokens():
    css = ps.PREMIUM_SCAFFOLD_FILES["/styles.css"]
    for token in ("--primary", "--success", "--warning", "--bg", "--surface", "--border"):
        assert f"{token}:" in css or f"{token} :" in css, f"{token} not defined"
    # locked palette values from the design doc §5.1
    assert "#020617" in css  # slate-950 background
    assert "#0f172a" in css  # surface
    assert "#F97316" in css or "#f97316" in css  # primary orange


def test_cheatsheet_is_frozen_reference_string():
    sheet = ps.premium_primitives_cheatsheet()
    assert isinstance(sheet, str) and sheet.strip()
    assert "../ui" in sheet
    for name in PRIMITIVE_NAMES:
        assert name in sheet, f"{name} missing from cheatsheet"


def test_scaffold_is_sandpack_compatible_and_declares_deps():
    files = {**ps.PREMIUM_SCAFFOLD_FILES, "/App.js": "export default ()=>null"}
    out = ensure_dependencies(files)
    assert is_sandpack_shaped(out)
    pkg = json.loads(out["/package.json"])
    deps = pkg["dependencies"]
    for dep in ("react", "react-dom", "lucide-react", "recharts"):
        assert dep in deps, f"{dep} not declared"


def test_primitive_js_uses_tokens_not_raw_hex():
    # Every JS primitive must reference colors via var(--...) and contain NO raw hex —
    # /styles.css is the single place hex literals may live (so re-theming via :root works).
    for path, source in ps.PREMIUM_SCAFFOLD_FILES.items():
        if not path.endswith(".js"):
            continue
        assert not _HEX_RE.search(source), f"{path} contains a raw hex color"
    # Colors are token-driven: primitives either reference var(--...) inline (e.g. KPIStat's
    # sparkline) or apply token-backed CSS classes defined in /styles.css. At minimum, inline
    # token usage must exist, and /styles.css must be var(--...) based so :root re-theming works.
    assert "var(--" in ps.PREMIUM_SCAFFOLD_FILES["/ui/KPIStat.js"]
    assert ps.PREMIUM_SCAFFOLD_FILES["/styles.css"].count("var(--") > 50


def test_styles_has_reset_animation_and_responsive_block():
    css = ps.PREMIUM_SCAFFOLD_FILES["/styles.css"]
    assert "@keyframes fadeInUp" in css
    assert "focus-visible" in css
    assert "@media" in css
    assert "::-webkit-scrollbar" in css


def test_sidebar_resolves_icon_name_strings():
    # Sidebar must resolve icon NAME STRINGS (the coder passes item.icon:"Users")
    # via the lucide namespace and never render the raw string as text.
    icon = ps.PREMIUM_SCAFFOLD_FILES["/ui/icon.js"]
    assert 'import * as LucideIcons from "lucide-react"' in icon
    assert "resolveIcon" in icon
    assert "LucideIcons[" in icon  # dynamic name lookup
    sidebar = ps.PREMIUM_SCAFFOLD_FILES["/ui/Sidebar.js"]
    assert "resolveIcon" in sidebar  # sidebar uses the resolver, not {item.icon}
    barrel = ps.PREMIUM_SCAFFOLD_FILES["/ui/index.js"]
    assert "resolveIcon" in barrel


def test_appshell_lays_out_topbar_on_top():
    shell = ps.PREMIUM_SCAFFOLD_FILES["/ui/AppShell.js"]
    assert "topbar" in shell and "sidebar" in shell and "children" in shell
    css = ps.PREMIUM_SCAFFOLD_FILES["/styles.css"]
    # Shell stacks a topbar row on top of a [sidebar | main] body row.
    assert ".app-shell-topbar" in css
    assert ".app-shell-body" in css
    assert ".app-main" in css


def test_chartcard_bounds_recharts_height():
    chart = ps.PREMIUM_SCAFFOLD_FILES["/ui/ChartCard.js"]
    assert "height" in chart and "chart-frame" in chart
    css = ps.PREMIUM_SCAFFOLD_FILES["/styles.css"]
    assert ".chart-frame" in css
    # Backstop so any recharts container is height-bounded.
    assert ".recharts-responsive-container" in css


def test_cheatsheet_mentions_appshell_chartcard_and_icon_string():
    sheet = ps.premium_primitives_cheatsheet()
    assert "AppShell" in sheet
    assert "ChartCard" in sheet
    # icon may be a lucide NAME STRING (documented for the coder)
    assert "NAME STRING" in sheet or "name string" in sheet.lower()
