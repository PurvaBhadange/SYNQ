"""
Projects API endpoints.
CRUD operations for SYNQ projects.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db.models import Project, ProjectDomain, ProjectStatus, Task

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    domain: ProjectDomain = ProjectDomain.GENERAL
    allowed_providers: Optional[List[str]] = None  # Empty = all allowed


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    domain: Optional[ProjectDomain] = None
    status: Optional[ProjectStatus] = None
    allowed_providers: Optional[List[str]] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    domain: str
    status: str
    allowed_providers: List[str]
    memory_graph_id: Optional[str]
    task_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status_filter: Optional[ProjectStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all projects, optionally filtered by status."""
    query = select(Project)
    if status_filter:
        query = query.where(Project.status == status_filter.value)
    query = query.order_by(Project.updated_at.desc())
    result = await db.execute(query)
    projects = result.scalars().all()

    responses = []
    for p in projects:
        # Count tasks
        task_count_query = select(Task).where(Task.project_id == p.id)
        task_result = await db.execute(task_count_query)
        count = len(task_result.scalars().all())
        responses.append(ProjectResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            domain=p.domain,
            status=p.status,
            allowed_providers=p.get_allowed_provider_list(),
            memory_graph_id=p.memory_graph_id,
            task_count=count,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ))
    return responses


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project."""
    project = Project(
        name=data.name,
        description=data.description,
        domain=data.domain.value,
        allowed_providers=",".join(data.allowed_providers) if data.allowed_providers else "",
    )
    db.add(project)
    await db.flush()  # Get ID without committing
    await db.refresh(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        domain=project.domain,
        status=project.status,
        allowed_providers=project.get_allowed_provider_list(),
        memory_graph_id=project.memory_graph_id,
        task_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get a project by ID."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    task_count_query = select(Task).where(Task.project_id == project_id)
    task_result = await db.execute(task_count_query)
    count = len(task_result.scalars().all())
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        domain=project.domain,
        status=project.status,
        allowed_providers=project.get_allowed_provider_list(),
        memory_graph_id=project.memory_graph_id,
        task_count=count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.domain is not None:
        project.domain = data.domain.value
    if data.status is not None:
        project.status = data.status.value
    if data.allowed_providers is not None:
        project.allowed_providers = ",".join(data.allowed_providers)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        domain=project.domain,
        status=project.status,
        allowed_providers=project.get_allowed_provider_list(),
        memory_graph_id=project.memory_graph_id,
        task_count=0,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a project and all its tasks."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    await db.delete(project)
