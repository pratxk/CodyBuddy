from pydantic import BaseModel, ConfigDict, Field


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


class CoderState(BaseModel):
    task_plan: TaskPlan = Field(description="The task plan being implemented")
    current_step_idx: int = Field(0, description="Index of the current implementation step")
