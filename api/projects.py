"""
Projects API — list and fetch saved projects by authenticated user.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from auth.dependencies import get_current_user
from db.database import SessionLocal
from db.models import Project, User

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
