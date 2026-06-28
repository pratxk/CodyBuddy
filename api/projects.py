"""
Projects API — list and fetch saved projects by session_id.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from db.database import SessionLocal
from db.models import Project

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
def list_projects(session_id: str = Query(..., description="Anonymous owner key")) -> list[ProjectSummary]:
    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    with SessionLocal() as db:
        rows = db.execute(
            select(Project)
            .where(Project.session_id == session_id)
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
def get_project(project_id: str, session_id: str = Query(..., description="Anonymous owner key")) -> ProjectDetail:
    if not session_id.strip():
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        pid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    with SessionLocal() as db:
        row = db.get(Project, pid)
    if not row or str(row.session_id) != session_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectDetail(
        id=str(row.id),
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        session_id=row.session_id,
        brief=row.brief,
        files=row.files,
    )
