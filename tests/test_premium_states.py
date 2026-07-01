"""Tests for premium-only pydantic schemas added to agent/states.py.

Verifies:
- PremiumPlan / PremiumView / Entity / PremiumViewSpec validate correctly.
- extra="ignore" tolerates unknown keys from LLM output.
- Optional list/dict fields default to empty collections.
- Existing Plan and TaskPlan are byte-for-byte untouched (regression).
"""
import pytest

from agent.states import (
    Entity,
    ImplementationTask,
    Plan,
    PremiumPlan,
    PremiumView,
    PremiumViewSpec,
    TaskPlan,
)


# ── Entity ────────────────────────────────────────────────────────────────────

def test_entity_required_fields():
    e = Entity(name="Client")
    assert e.name == "Client"
    assert e.fields == []


def test_entity_with_fields():
    e = Entity(name="LoanApplication", fields=["id", "status", "amount"])
    assert e.fields == ["id", "status", "amount"]


def test_entity_extra_ignored():
    e = Entity(name="Applicant", fields=[], unknown_key="surprise")
    assert not hasattr(e, "unknown_key")


# ── PremiumView ───────────────────────────────────────────────────────────────

def test_premium_view_required_fields():
    v = PremiumView(
        id="client-onboarding",
        label="Client Onboarding",
        icon="Users",
        purpose="Capture and verify new client details",
    )
    assert v.id == "client-onboarding"
    assert v.label == "Client Onboarding"
    assert v.icon == "Users"
    assert v.purpose == "Capture and verify new client details"
    assert v.kpis == []
    assert v.table_columns == []
    assert v.actions == []


def test_premium_view_with_all_fields():
    v = PremiumView(
        id="loan-review",
        label="Loan Review",
        icon="FileText",
        purpose="Review and approve loan applications",
        kpis=["Total Applications", "Approval Rate", "Avg Processing Time"],
        table_columns=["Applicant", "Amount", "Status", "Submitted"],
        actions=["approve", "reject", "open-modal"],
    )
    assert v.kpis == ["Total Applications", "Approval Rate", "Avg Processing Time"]
    assert v.table_columns == ["Applicant", "Amount", "Status", "Submitted"]
    assert v.actions == ["approve", "reject", "open-modal"]


def test_premium_view_extra_ignored():
    v = PremiumView(
        id="disbursement",
        label="Disbursement",
        icon="DollarSign",
        purpose="Disburse approved loans",
        phantom_field="should be dropped",
    )
    assert not hasattr(v, "phantom_field")


# ── PremiumPlan ───────────────────────────────────────────────────────────────

def _make_premium_plan() -> PremiumPlan:
    """Helper: build a valid PremiumPlan with 2 views + entities."""
    return PremiumPlan(
        name="Rapid Loan Origination",
        palette={"--primary": "#F97316", "--success": "#14b8a6"},
        entities=[
            Entity(name="Client", fields=["id", "name", "email"]),
            Entity(name="LoanApplication", fields=["id", "client_id", "amount", "status"]),
        ],
        views=[
            PremiumView(
                id="client-onboarding",
                label="Client Onboarding",
                icon="Users",
                purpose="Capture and verify new client details",
                kpis=["New Clients Today", "Verified %"],
                table_columns=["Name", "Email", "KYC Status", "Date"],
                actions=["verify", "reject"],
            ),
            PremiumView(
                id="loan-review",
                label="Loan Review",
                icon="FileText",
                purpose="Review and approve loan applications",
                kpis=["Pending Applications", "Approval Rate"],
                table_columns=["Applicant", "Amount", "Score", "Status"],
                actions=["approve", "reject", "open-modal"],
            ),
        ],
        mock_data_spec=(
            "A client onboarded on day 1 progresses to loan review on day 2 "
            "and is approved on day 3, appearing as 'approved' in disbursement."
        ),
    )


def test_premium_plan_fields_round_trip():
    plan = _make_premium_plan()
    assert plan.name == "Rapid Loan Origination"
    assert plan.palette == {"--primary": "#F97316", "--success": "#14b8a6"}
    assert len(plan.entities) == 2
    assert plan.entities[0].name == "Client"
    assert len(plan.views) == 2
    assert plan.views[0].id == "client-onboarding"
    assert plan.views[1].id == "loan-review"
    assert "approved" in plan.mock_data_spec


def test_premium_plan_defaults():
    plan = PremiumPlan(name="Minimal App")
    assert plan.palette == {}
    assert plan.entities == []
    assert plan.views == []
    assert plan.mock_data_spec == ""


def test_premium_plan_extra_key_ignored():
    """LLM may emit unknown keys; extra='ignore' must swallow them silently."""
    data = {
        "name": "CRM Suite",
        "palette": {},
        "views": [],
        "entities": [],
        "mock_data_spec": "",
        "totally_unknown_llm_field": "oops",
        "another_extra": 42,
    }
    plan = PremiumPlan(**data)
    assert plan.name == "CRM Suite"
    assert not hasattr(plan, "totally_unknown_llm_field")
    assert not hasattr(plan, "another_extra")


def test_premium_plan_serialization_round_trip():
    plan = _make_premium_plan()
    dumped = plan.model_dump()
    restored = PremiumPlan(**dumped)
    assert restored.name == plan.name
    assert restored.palette == plan.palette
    assert len(restored.views) == len(plan.views)
    assert restored.views[0].id == plan.views[0].id


# ── PremiumViewSpec ───────────────────────────────────────────────────────────

def test_premium_view_spec_required_fields():
    spec = PremiumViewSpec(
        view_id="client-onboarding",
        filepath="/views/ClientOnboarding.js",
        task_description="Build the client onboarding step with KPI stats and a data table.",
    )
    assert spec.view_id == "client-onboarding"
    assert spec.filepath == "/views/ClientOnboarding.js"
    assert spec.task_description.startswith("Build")
    assert spec.primitives == []
    assert spec.data_keys == []


def test_premium_view_spec_with_all_fields():
    spec = PremiumViewSpec(
        view_id="loan-review",
        filepath="/views/LoanReview.js",
        task_description="Display pending loan applications with approve/reject actions.",
        primitives=["KPIStat", "DataTable", "Badge", "Button", "Modal"],
        data_keys=["loanApplications", "kpiMetrics"],
    )
    assert spec.primitives == ["KPIStat", "DataTable", "Badge", "Button", "Modal"]
    assert spec.data_keys == ["loanApplications", "kpiMetrics"]


def test_premium_view_spec_extra_ignored():
    spec = PremiumViewSpec(
        view_id="disbursement",
        filepath="/views/Disbursement.js",
        task_description="Handle loan disbursement.",
        extra_llm_key="noise",
    )
    assert not hasattr(spec, "extra_llm_key")


# ── Regression: standard Plan and TaskPlan are unchanged ─────────────────────

def test_plan_still_validates():
    plan = Plan(
        name="My App",
        description="A simple to-do app",
        techStack=["React", "FastAPI"],
        features=["Add tasks", "Delete tasks"],
        files=[],
    )
    assert plan.name == "My App"
    assert plan.techStack == ["React", "FastAPI"]


def test_plan_extra_ignored():
    """Plan also has extra='ignore' — must continue to work."""
    plan = Plan(
        name="Todo App",
        description="Simple todo",
        techStack=["React"],
        features=["Add"],
        files=[],
        unexpected_key="value",
    )
    assert plan.name == "Todo App"
    assert not hasattr(plan, "unexpected_key")


def test_task_plan_still_validates():
    task_plan = TaskPlan(
        implementation_steps=[
            ImplementationTask(
                filepath="/App.js",
                task_description="Create the root React component.",
            )
        ]
    )
    assert len(task_plan.implementation_steps) == 1
    assert task_plan.implementation_steps[0].filepath == "/App.js"


def test_task_plan_extra_ignored():
    task_plan = TaskPlan(
        implementation_steps=[],
        stray_key="should be dropped",
    )
    assert task_plan.implementation_steps == []
    assert not hasattr(task_plan, "stray_key")
