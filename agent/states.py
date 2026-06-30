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
