from pydantic import BaseModel, ConfigDict, Field, field_validator

from agent.scaffold import coerce_framework


class File(BaseModel):
    """A file the app needs. Content is produced later by the coder, not the planner."""
    path: str = Field(description="The relative path of the file to be created")
    purpose: str = Field(description="A one-line description of what this file is for")


class Plan(BaseModel):
    name: str = Field(description="The name of the app to be built")
    description: str = Field(description="A one-line description of the app to be built")
    techStack: list[str] = Field(description="The technologies to be used")
    features: list[str] = Field(description="The features to be implemented")
    files: list[File] = Field(description="The files to be created, with path and purpose")

    model_config = ConfigDict(extra="ignore")


class ImplementationTask(BaseModel):
    filepath: str = Field(description="The path to the file to be created or modified")
    task_description: str = Field(
        description="A detailed, self-contained description of what to implement in this file"
    )

    model_config = ConfigDict(extra="ignore")


class TaskPlan(BaseModel):
    implementation_steps: list[ImplementationTask] = Field(
        description="Ordered steps to implement the app, dependencies first"
    )

    model_config = ConfigDict(extra="ignore")


class Entity(BaseModel):
    """A domain entity in the dashboard's data model."""
    name: str = Field(description="The entity name (e.g. 'Client', 'LoanApplication')")
    fields: list[str] = Field(
        default_factory=list,
        description="Column/attribute names for this entity",
    )

    model_config = ConfigDict(extra="ignore")


class PremiumView(BaseModel):
    """One workflow step = one sidebar item = one generated view."""
    id: str = Field(description="Stable slug, e.g. 'client-onboarding'")
    label: str = Field(description="Sidebar label for this step")
    icon: str = Field(description="Lucide icon name, e.g. 'Users'")
    purpose: str = Field(description="One-line description of what this step does")
    kpis: list[str] = Field(
        default_factory=list,
        description="KPI labels for this view",
    )
    table_columns: list[str] = Field(
        default_factory=list,
        description="Data-table columns for this view",
    )
    actions: list[str] = Field(
        default_factory=list,
        description="Button actions, e.g. 'approve', 'reject', 'open-modal'",
    )

    model_config = ConfigDict(extra="ignore")


class PremiumPlan(BaseModel):
    """The premium planner's output — extends the domain design."""
    name: str = Field(description="The app name")
    palette: dict[str, str] = Field(
        default_factory=dict,
        description="CSS-var overrides, e.g. {'--primary': '#F97316'}",
    )
    entities: list[Entity] = Field(
        default_factory=list,
        description="Domain entities in the dashboard's data model",
    )
    views: list[PremiumView] = Field(
        default_factory=list,
        description="Ordered workflow steps (= sidebar views)",
    )
    mock_data_spec: str = Field(
        default="",
        description="Prose describing the cross-step story the mock data must tell",
    )

    model_config = ConfigDict(extra="ignore")


class PremiumViewSpec(BaseModel):
    """The premium architect's per-view build spec."""
    view_id: str = Field(description="Matches a PremiumView.id")
    filepath: str = Field(description="e.g. '/views/ClientOnboarding.js'")
    task_description: str = Field(description="What to build in this view")
    primitives: list[str] = Field(
        default_factory=list,
        description="Baked primitives to compose, e.g. ['KPIStat','DataTable','Badge','Button']",
    )
    data_keys: list[str] = Field(
        default_factory=list,
        description="Mock-data keys this view reads",
    )

    model_config = ConfigDict(extra="ignore")


class PremiumArchitecture(BaseModel):
    """The premium architect's output: one build spec per view plus the shared
    /data/mock.js schema every view and the shell agree on."""
    view_specs: list[PremiumViewSpec] = Field(
        default_factory=list,
        description="One PremiumViewSpec per workflow step, in dependency order",
    )
    mock_schema: str = Field(
        default="",
        description="The shared /data/mock.js schema (keys + types) shell + views agree on",
    )

    model_config = ConfigDict(extra="ignore")


class IntakeStep(BaseModel):
    """One turn of the self-gating intake loop.

    Either ready (with a consolidated build brief) OR asking ONE more question
    (with a few selectable options). Never both — but the endpoint tolerates
    partial output and fills gaps defensively.
    """
    ready: bool = Field(description="True if the request is specific enough to build")
    question: str | None = Field(
        default=None, description="The single next clarifying question (when not ready)"
    )
    options: list[str] = Field(
        default_factory=list, description="2-4 short, selectable answer options for the question"
    )
    brief: str | None = Field(
        default=None, description="Consolidated 1-3 sentence build brief (when ready)"
    )
    framework: str = Field(
        default="react",
        description='Framework to build as: "react" (default) | "static" | "nextjs"',
    )

    @field_validator("framework", mode="before")
    @classmethod
    def _coerce_framework(cls, v):
        # ponytail: validate at the boundary — unknown/invalid framework → "react".
        return coerce_framework(v)

    model_config = ConfigDict(extra="ignore")
