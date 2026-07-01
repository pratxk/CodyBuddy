"""Tests for the SPECIALIZED premium dashboard prompts (Phase 2) in agent/prompts.py.

Verifies:
- PREMIUM_DASHBOARD_GUIDELINES encodes the dark-palette + shell + KPI/table/badge/
  functional-button + cross-step mock-data rules.
- premium_planner_prompt embeds the user prompt + the 4-6 WORKFLOW STEPS instruction.
- coder_shell_prompt / coder_view_prompt inject the primitives cheatsheet + the
  `=== FILE:` output contract; coder_view_prompt keeps input small (data_keys +
  palette, NO full mock-data dump).
- premium_coder_system_prompt extends the react CODER_SYSTEM_PROMPT with kit rules.
- REGRESSION: the standard prompt functions are byte-for-byte unchanged (hash snapshot).
"""
import hashlib

from agent import prompts as p
from agent.premium_scaffold import premium_primitives_cheatsheet


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


# ── PREMIUM_DASHBOARD_GUIDELINES ──────────────────────────────────────────────

def test_guidelines_dark_palette():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    assert "#020617" in g  # slate-950 background
    assert "#F97316" in g  # orange primary
    assert "orange" in g.lower()
    # semantic accents
    assert "teal" in g.lower()
    assert "amber" in g.lower()


def test_guidelines_css_vars_not_raw_hex():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    assert "var(--" in g
    assert "styles.css" in g


def test_guidelines_shell_sidebar_activeview_no_router():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    low = g.lower()
    assert "sidebar" in low
    assert "activeView" in g
    assert "no router" in low or "no react-router" in low or "router" in low
    assert "topbar" in low


def test_guidelines_every_view_requirements():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    assert "KPIStat" in g or "KPI" in g
    assert "DataTable" in g
    assert "search" in g.lower()
    assert "sort" in g.lower()
    assert "Badge" in g
    assert "ProgressBar" in g


def test_guidelines_functional_buttons():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    low = g.lower()
    assert "modal" in low
    assert "toast" in low
    # buttons must DO something (state mutation)
    assert "state" in low


def test_guidelines_cross_step_mock_data():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    assert "/data/mock.js" in g
    low = g.lower()
    assert "across steps" in low or "cross-step" in low or "flows across" in low


def test_guidelines_compose_not_handroll():
    g = p.PREMIUM_DASHBOARD_GUIDELINES
    low = g.lower()
    assert "../ui" in g
    assert "compose" in low
    assert "hand-roll" in low or "never" in low


# ── premium_planner_prompt ────────────────────────────────────────────────────

def test_planner_embeds_user_prompt():
    out = p.premium_planner_prompt("build a loan origination tool")
    assert "build a loan origination tool" in out


def test_planner_workflow_steps_instruction():
    out = p.premium_planner_prompt("build a loan origination tool")
    assert "4" in out and "6" in out
    assert "WORKFLOW STEP" in out.upper()


def test_planner_emits_premium_plan_fields():
    out = p.premium_planner_prompt("build an HR onboarding tool")
    for token in ["palette", "views", "icon", "kpis", "table_columns",
                  "actions", "entities", "mock_data_spec"]:
        assert token in out, token


# ── premium_architect_prompt ──────────────────────────────────────────────────

def test_architect_embeds_plan_json():
    out = p.premium_architect_prompt('{"name": "LoanFlow"}')
    assert '{"name": "LoanFlow"}' in out


def test_architect_view_spec_and_shell_first():
    out = p.premium_architect_prompt('{"name": "X"}')
    assert "PremiumViewSpec" in out
    assert "primitives" in out
    low = out.lower()
    assert "shell" in low and "mock" in low
    assert "first" in low  # order shell + mock-data first


# ── coder_shell_prompt ────────────────────────────────────────────────────────

def test_shell_embeds_cheatsheet():
    out = p.coder_shell_prompt('{"name": "X"}', "{applications: [...]}")
    # a known primitive name/prop from the cheatsheet must be present
    assert "KPIStat" in out
    assert "DataTable" in out
    assert premium_primitives_cheatsheet() in out


def test_shell_file_contract_and_targets():
    out = p.coder_shell_prompt('{"name": "X"}', "{applications: [...]}")
    assert "=== FILE:" in out
    assert "/App.js" in out
    assert "/data/mock.js" in out
    assert "activeView" in out
    assert "ToastHost" in out


def test_shell_embeds_mock_schema():
    out = p.coder_shell_prompt('{"name": "X"}', "SCHEMA_MARKER_123")
    assert "SCHEMA_MARKER_123" in out


# ── coder_view_prompt ─────────────────────────────────────────────────────────

def test_view_embeds_cheatsheet_and_contract():
    out = p.coder_view_prompt('{"filepath": "/views/Underwriting.js"}',
                              ["applications", "officers"], {"--primary": "#F97316"})
    assert premium_primitives_cheatsheet() in out
    assert "DataTable" in out
    assert "=== FILE:" in out
    assert "../ui" in out


def test_view_embeds_data_keys_and_palette():
    out = p.coder_view_prompt('{"filepath": "/views/X.js"}',
                              ["applications", "officers"], {"--primary": "#EF4444"})
    assert "applications" in out
    assert "officers" in out
    assert "--primary" in out
    assert "#EF4444" in out


def test_view_does_not_dump_full_mock_data():
    # Input must stay small: only data KEYS, not row-level values.
    out = p.coder_view_prompt('{"filepath": "/views/X.js"}',
                              ["applications"], {"--primary": "#F97316"})
    assert "SENSITIVE_ROW_VALUE" not in out  # sanity: no accidental data injection
    # the prompt should reference reading from ../data/mock, not inline the data
    assert "../data/mock" in out


# ── premium_coder_system_prompt ───────────────────────────────────────────────

def test_system_prompt_extends_react_coder():
    out = p.premium_coder_system_prompt()
    # contains the original react system prompt in full
    assert p.CODER_SYSTEM_PROMPT in out
    low = out.lower()
    assert "../ui" in out
    assert "../data" in out
    assert "never redefine" in low or "not redefine" in low or "redefine" in low


# ── REGRESSION: standard prompts byte-for-byte unchanged ──────────────────────

def test_standard_prompts_unchanged_snapshot():
    assert _h(p.DESIGN_GUIDELINES) == (
        "c46c5ff9d283e9f0e704ec78034b937ff2bca2aaf526ab531e6cd53ce133d0b8"
    )
    assert _h(p.planner_prompt("build a todo app")) == (
        "a1ef9ff6871935848240a5ea612110d9649fa54bdda25ea98527aebf07344ce2"
    )
    assert _h(p.architect_prompt('{"name": "X"}')) == (
        "a46ecdfe3095c21e65689f0fbe6ab234726bef0378db1c664cf698a0728548ec"
    )
    assert _h(p.coder_prompt([{"filepath": "/App.js", "task_description": "root"}],
                             '{"name": "X"}')) == (
        "548b841209a0cad973aad747b920445aaf757e47fa5b83cb347d4516489ecce5"
    )
    assert _h(p.coder_system_prompt()) == (
        "6f41b4ce9555d8c002edce00e7d9776f28f17a7ee5bd317bd2807c01bed51651"
    )
