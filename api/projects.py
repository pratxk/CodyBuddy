"""
Projects API — list and fetch saved projects by authenticated user.
"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from agent.scaffold import slugify, to_vite_project
from auth.crypto import decrypt
from auth.dependencies import get_current_user
from db.database import SessionLocal
from db.models import Project, User
from integrations.github_client import GitHubError, publish_files

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    session_id: str
    brief: str
    files: dict


@router.get("", response_model=list[ProjectSummary])
def list_projects(current_user: User = Depends(get_current_user)) -> list[ProjectSummary]:
    with SessionLocal() as db:
        rows = db.execute(
            select(Project)
            .where(Project.user_id == current_user.id)
            .order_by(Project.created_at.desc())
        ).scalars().all()
    return [
        ProjectSummary(
            id=str(r.id),
            title=r.title,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, current_user: User = Depends(get_current_user)) -> ProjectDetail:
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    with SessionLocal() as db:
        row = db.get(Project, pid)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectDetail(
        id=str(row.id),
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        session_id=row.session_id or "",
        brief=row.brief,
        files=row.files,
    )


class PublishResponse(BaseModel):
    repo_url: str
    vercel_import_url: str


@router.post("/{project_id}/publish", response_model=PublishResponse)
def publish_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
) -> PublishResponse:
    """Transform a project's Sandpack files into a Vite repo and push it to the user's GitHub."""
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    with SessionLocal() as db:
        row = db.get(Project, pid)
    if not row or row.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    enc = getattr(current_user, "github_token_enc", None)
    if not (isinstance(enc, str) and enc):
        raise HTTPException(status_code=400, detail="Connect GitHub first")
    token = decrypt(enc)

    vite_files = to_vite_project(row.files, row.title)
    repo_name = f"appsmith-{slugify(row.title)}"
    try:
        repo_url = publish_files(token, repo_name, vite_files)
    except GitHubError as exc:
        logger.error("GitHub publish failed for project %s: %s", project_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except ValueError:
        # ponytail: stored token no longer valid — never echo it.
        raise HTTPException(status_code=400, detail="GitHub token is no longer valid; reconnect GitHub")

    return PublishResponse(
        repo_url=repo_url,
        vercel_import_url=f"https://vercel.com/new/clone?repository-url={repo_url}",
    )
