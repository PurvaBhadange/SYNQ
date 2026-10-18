"""
Tasks API endpoints for SYNQ.
Handles task creation, DAG decomposition planning, task execution, approval workflow,
rejection, editing, and dependency validation.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional

from core.coordinator import coordinator
from core.planner import planner
from db.models import Project, Task, TaskExecution, TaskStatus, TaskType
from db.session import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from memory.memory_service import memory_service
from memory.falkordb_client import FalkorDBConnectionError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    task_type: str = Field(default="general")
    priority: int = Field(default=5, ge=1, le=10)
    acceptance_criteria: Optional[str] = None
    dependencies: Optional[List[str]] = Field(default_factory=list)
    requires_approval: bool = False


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=5)
    domain: Optional[str] = None


class ExecuteRequest(BaseModel):
    user_override_provider: Optional[str] = None
    user_override_model: Optional[str] = None


class TaskApprovalRequest(BaseModel):
    reason: Optional[str] = "Approved by operator"
    approver: Optional[str] = "Human Operator"
    user_override_provider: Optional[str] = None
    user_override_model: Optional[str] = None


class TaskRejectionRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for rejection")
    approver: Optional[str] = "Human Operator"


class TaskEditRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    task_type: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    dependencies: Optional[List[str]] = None
    requires_approval: Optional[bool] = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    parent_task_id: Optional[str]
    title: str
    description: Optional[str]
    task_type: str
    status: str
    priority: int
    acceptance_criteria: Optional[str]
    dependencies: List[str]
    assigned_provider: Optional[str]
    assigned_model: Optional[str]
    requires_approval: bool
    approval_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_project_tasks(project_id: str, db: AsyncSession = Depends(get_db)):
    """List all tasks belonging to a project."""
    res = await db.execute(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.created_at.asc())
    )
    tasks = res.scalars().all()
    return [
        TaskResponse(
            id=t.id,
            project_id=t.project_id,
            parent_task_id=t.parent_task_id,
            title=t.title,
            description=t.description,
            task_type=t.task_type,
            status=t.status,
            priority=t.priority,
            acceptance_criteria=t.acceptance_criteria,
            dependencies=t.get_dependency_list(),
            assigned_provider=t.assigned_provider,
            assigned_model=t.assigned_model,
            requires_approval=t.requires_approval,
            approval_reason=t.approval_reason,
            rejection_reason=t.rejection_reason,
            approved_at=t.approved_at.isoformat() if t.approved_at else None,
            approved_by=t.approved_by,
            created_at=t.created_at.isoformat() if t.created_at else "",
            started_at=t.started_at.isoformat() if t.started_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
        )
        for t in tasks
    ]


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: str,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new task in a project."""
    p_res = await db.execute(select(Project).where(Project.id == project_id))
    project = p_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        task_type=payload.task_type,
        priority=payload.priority,
        acceptance_criteria=payload.acceptance_criteria,
        dependencies=",".join(payload.dependencies) if payload.dependencies else None,
        requires_approval=payload.requires_approval,
        status=TaskStatus.PENDING.value,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Register in FalkorDB (safely handle paused/offline FalkorDB)
    try:
        memory_service.create_task_node(
            project_id=project_id,
            task_id=task.id,
            title=task.title,
            task_type=task.task_type,
            priority=task.priority,
        )
        if payload.dependencies:
            for dep in payload.dependencies:
                memory_service.link_task_dependency(project_id, task.id, dep)
    except FalkorDBConnectionError as exc:
        logger.warning("FalkorDB offline during task creation: %s. Operational record persisted in SQLite.", exc)

    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        parent_task_id=task.parent_task_id,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        status=task.status,
        priority=task.priority,
        acceptance_criteria=task.acceptance_criteria,
        dependencies=task.get_dependency_list(),
        assigned_provider=task.assigned_provider,
        assigned_model=task.assigned_model,
        requires_approval=task.requires_approval,
        approval_reason=task.approval_reason,
        rejection_reason=task.rejection_reason,
        approved_at=task.approved_at.isoformat() if task.approved_at else None,
        approved_by=task.approved_by,
        created_at=task.created_at.isoformat(),
        started_at=None,
        completed_at=None,
    )


@router.post("/projects/{project_id}/plan")
async def plan_project(
    project_id: str,
    payload: PlanRequest,
    db: AsyncSession = Depends(get_db),
):
    """Decompose high-level goal into DAG of tasks using deterministic planner."""
    p_res = await db.execute(select(Project).where(Project.id == project_id))
    project = p_res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    domain = payload.domain or project.domain
    plan_result = planner.plan(goal=payload.goal, domain=domain)

    index_to_task_id: Dict[int, str] = {}
    created_tasks: List[Task] = []

    for item in plan_result.tasks:
        task = Task(
            project_id=project_id,
            title=item.title,
            description=item.description,
            task_type=item.task_type,
            priority=item.priority,
            acceptance_criteria=item.acceptance_criteria,
            requires_approval=item.requires_approval,
            status=TaskStatus.PENDING.value,
        )
        db.add(task)
        await db.flush()
        index_to_task_id[item.index] = task.id
        created_tasks.append(task)

    for item in plan_result.tasks:
        if item.dependencies:
            task_id = index_to_task_id[item.index]
            dep_ids = [index_to_task_id[d] for d in item.dependencies if d in index_to_task_id]
            t_res = await db.execute(select(Task).where(Task.id == task_id))
            t = t_res.scalar_one()
            t.dependencies = ",".join(dep_ids)

            # Link in FalkorDB
            for dep_id in dep_ids:
                try:
                    memory_service.link_task_dependency(project_id, task_id, dep_id)
                except FalkorDBConnectionError:
                    pass

    for task in created_tasks:
        try:
            memory_service.create_task_node(
                project_id=project_id,
                task_id=task.id,
                title=task.title,
                task_type=task.task_type,
                priority=task.priority,
            )
        except FalkorDBConnectionError:
            pass

    await db.commit()

    return {
        "status": "planned",
        "planner_type": plan_result.planner_type,
        "reasoning": plan_result.reasoning,
        "task_count": len(created_tasks),
        "execution_order": [index_to_task_id[i] for i in plan_result.execution_order if i in index_to_task_id],
    }


@router.post("/tasks/{task_id}/execute")
async def execute_task_endpoint(task_id: str, payload: Optional[ExecuteRequest] = None):
    """Trigger execution of a task with routing, streaming, and validation."""
    override_p = payload.user_override_provider if payload else None
    override_m = payload.user_override_model if payload else None

    result = await coordinator.execute_task(
        task_id=task_id,
        user_override_provider=override_p,
        user_override_model=override_m,
    )
    return result


@router.get("/tasks/{task_id}/approval_context")
async def get_task_approval_context(task_id: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve comprehensive approval context for human-in-the-loop review:
    - Task details & objective
    - Upstream dependency outputs
    - Provider assignment and proposed action
    - Potential risk analysis
    """
    res = await db.execute(
        select(Task)
        .options(selectinload(Task.executions))
        .where(Task.id == task_id)
    )
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Fetch upstream dependency details
    dep_ids = task.get_dependency_list()
    upstream_details = []
    dependencies_all_completed = True

    if dep_ids:
        dep_res = await db.execute(
            select(Task)
            .options(selectinload(Task.executions))
            .where(Task.id.in_(dep_ids))
        )
        dep_tasks = dep_res.scalars().all()
        for d in dep_tasks:
            latest_exec = d.executions[-1] if d.executions else None
            is_completed = (d.status == TaskStatus.COMPLETED.value)
            if not is_completed:
                dependencies_all_completed = False
            upstream_details.append({
                "task_id": d.id,
                "title": d.title,
                "status": d.status,
                "task_type": d.task_type,
                "is_completed": is_completed,
                "latest_output_preview": (latest_exec.output_raw[:250] + "...") if (latest_exec and latest_exec.output_raw) else None,
            })

    # Risk assessment
    risks = []
    if task.task_type == TaskType.CODE.value:
        risks.append("Generates executable code; require verification before running in production.")
    if not dependencies_all_completed:
        risks.append("Warning: Upstream dependencies are not yet completed.")
    if task.priority >= 8:
        risks.append("High priority task with critical path downstream impact.")
    if not risks:
        risks.append("Standard automated execution; low inherent risk.")

    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "priority": task.priority,
        "status": task.status,
        "requires_approval": task.requires_approval,
        "acceptance_criteria": task.acceptance_criteria,
        "assigned_provider": task.assigned_provider,
        "assigned_model": task.assigned_model,
        "upstream_dependencies": upstream_details,
        "dependencies_all_completed": dependencies_all_completed,
        "approval_reason": task.approval_reason,
        "rejection_reason": task.rejection_reason,
        "approved_by": task.approved_by,
        "approved_at": task.approved_at.isoformat() if task.approved_at else None,
        "risks": risks,
        "available_actions": ["approve", "reject", "edit"],
    }


@router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    payload: Optional[TaskApprovalRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a task that was awaiting human approval.
    Enforces:
    - State transition check (task MUST be in awaiting_approval status).
    - Prevents duplicate approval requests or approval of running/completed tasks.
    - Validates upstream dependencies before execution.
    - Records audit log (approver, reason, timestamp).
    - Executes via coordinator with audit log persisted.
    """
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Protection against duplicate approval and invalid state transitions
    current_status = task.status.value if hasattr(task.status, "value") else str(task.status)
    if current_status != TaskStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve task in '{current_status}' state. Only tasks awaiting approval can be approved.",
        )

    # Dependency check before execution
    dep_ids = task.get_dependency_list()
    if dep_ids:
        dep_res = await db.execute(select(Task).where(Task.id.in_(dep_ids)))
        dep_tasks = dep_res.scalars().all()
        incomplete = [d for d in dep_tasks if d.status != TaskStatus.COMPLETED.value]
        if incomplete:
            names = [f"{d.title} ({d.status})" for d in incomplete]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute approved task: upstream dependencies not completed: {', '.join(names)}",
            )

    # Record approval audit trail
    reason = (payload.reason if payload and payload.reason else "Approved by human operator")
    approver = (payload.approver if payload and payload.approver else "Human Operator")
    task.status = TaskStatus.ASSIGNED.value
    task.approval_reason = reason
    task.rejection_reason = None
    task.approved_by = approver
    task.approved_at = datetime.now(timezone.utc)
    await db.commit()

    # Emit real-time WebSocket event
    await coordinator.emit_event(
        task.project_id,
        "task_approved",
        {
            "task_id": task.id,
            "title": task.title,
            "approved_by": approver,
            "reason": reason,
        },
    )

    # Execute through existing coordinator
    override_p = payload.user_override_provider if payload else None
    override_m = payload.user_override_model if payload else None

    result = await coordinator.execute_task(
        task_id=task_id,
        user_override_provider=override_p,
        user_override_model=override_m,
    )

    return {
        "status": "approved",
        "task_id": task_id,
        "approved_by": approver,
        "approval_reason": reason,
        "execution_result": result,
    }


@router.post("/tasks/{task_id}/reject")
async def reject_task(
    task_id: str,
    payload: TaskRejectionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a pending or awaiting-approval task.
    Enforces:
    - Rejection is recorded with explicit reason.
    - Prevents downstream execution by marking dependent tasks BLOCKED.
    - Rejects invalid state transitions (cannot reject running or completed tasks).
    """
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    current_status = task.status.value if hasattr(task.status, "value") else str(task.status)
    if current_status in (TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject task currently in '{current_status}' state.",
        )

    task.status = TaskStatus.REJECTED.value
    task.rejection_reason = payload.reason
    task.approval_reason = None
    await db.commit()

    # Find and update any dependent tasks in this project to BLOCKED
    p_tasks_res = await db.execute(select(Task).where(Task.project_id == task.project_id))
    all_tasks = p_tasks_res.scalars().all()
    blocked_count = 0
    for t in all_tasks:
        deps = t.get_dependency_list()
        if task.id in deps and t.status in (TaskStatus.PENDING.value, TaskStatus.AWAITING_APPROVAL.value):
            t.status = TaskStatus.BLOCKED.value
            blocked_count += 1

    await db.commit()

    # Emit real-time WebSocket event
    await coordinator.emit_event(
        task.project_id,
        "task_rejected",
        {
            "task_id": task.id,
            "title": task.title,
            "reason": payload.reason,
            "blocked_downstream_count": blocked_count,
        },
    )

    return {
        "status": "rejected",
        "task_id": task.id,
        "reason": payload.reason,
        "blocked_downstream_count": blocked_count,
    }


@router.post("/tasks/{task_id}/edit")
async def edit_and_resubmit_task(
    task_id: str,
    payload: TaskEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Edit and resubmit a task (especially useful after rejection or awaiting approval).
    Allows modifying title, description, criteria, priority, and resubmitting.
    """
    res = await db.execute(select(Task).where(Task.id == task_id))
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    current_status = task.status.value if hasattr(task.status, "value") else str(task.status)
    if current_status in (TaskStatus.RUNNING.value, TaskStatus.COMPLETED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit task currently in '{current_status}' state.",
        )

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.acceptance_criteria is not None:
        task.acceptance_criteria = payload.acceptance_criteria
    if payload.task_type is not None:
        task.task_type = payload.task_type
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.dependencies is not None:
        task.dependencies = ",".join(payload.dependencies) if payload.dependencies else None
    if payload.requires_approval is not None:
        task.requires_approval = payload.requires_approval

    # Reset rejected or blocked status to pending (or awaiting_approval if required)
    if task.status in (TaskStatus.REJECTED.value, TaskStatus.BLOCKED.value, TaskStatus.FAILED.value):
        task.status = TaskStatus.PENDING.value
        task.rejection_reason = None

    await db.commit()
    await db.refresh(task)

    # Update FalkorDB node if available
    try:
        memory_service.create_task_node(
            project_id=task.project_id,
            task_id=task.id,
            title=task.title,
            task_type=task.task_type,
            priority=task.priority,
        )
    except FalkorDBConnectionError:
        pass

    await coordinator.emit_event(
        task.project_id,
        "task_updated",
        {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
        },
    )

    return TaskResponse(
        id=task.id,
        project_id=task.project_id,
        parent_task_id=task.parent_task_id,
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        status=task.status,
        priority=task.priority,
        acceptance_criteria=task.acceptance_criteria,
        dependencies=task.get_dependency_list(),
        assigned_provider=task.assigned_provider,
        assigned_model=task.assigned_model,
        requires_approval=task.requires_approval,
        approval_reason=task.approval_reason,
        rejection_reason=task.rejection_reason,
        approved_at=task.approved_at.isoformat() if task.approved_at else None,
        approved_by=task.approved_by,
        created_at=task.created_at.isoformat() if task.created_at else "",
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


@router.get("/tasks/{task_id}/detail")
async def get_task_detail(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get full task details including executions and routing decisions."""
    res = await db.execute(
        select(Task)
        .options(selectinload(Task.executions).selectinload(TaskExecution.routing_decision))
        .where(Task.id == task_id)
    )
    task = res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    executions_data = []
    for ex in task.executions:
        rd = ex.routing_decision
        executions_data.append({
            "id": ex.id,
            "attempt": ex.attempt_number,
            "provider_id": ex.provider_id,
            "model_id": ex.model_id,
            "status": ex.status,
            "output": ex.output_raw,
            "validation_passed": ex.validation_passed,
            "validation_result": json.loads(ex.validation_result) if ex.validation_result else None,
            "error_message": ex.error_message,
            "is_fallback": ex.is_fallback,
            "fallback_reason": ex.fallback_reason,
            "routing_decision": {
                "selected_provider": rd.selected_provider if rd else ex.provider_id,
                "selected_model": rd.selected_model if rd else ex.model_id,
                "selection_reason": rd.selection_reason if rd else None,
                "rejected_providers": json.loads(rd.rejected_providers) if rd and rd.rejected_providers else [],
            } if rd else None,
        })

    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "acceptance_criteria": task.acceptance_criteria,
        "dependencies": task.get_dependency_list(),
        "assigned_provider": task.assigned_provider,
        "assigned_model": task.assigned_model,
        "requires_approval": task.requires_approval,
        "approval_reason": task.approval_reason,
        "rejection_reason": task.rejection_reason,
        "approved_at": task.approved_at.isoformat() if task.approved_at else None,
        "approved_by": task.approved_by,
        "executions": executions_data,
    }


# ── Interactive Visual DAG Canvas Endpoints ────────────────────────────────────

class DependencyModificationRequest(BaseModel):
    task_id: str = Field(..., description="The task that will depend on another task")
    depends_on_task_id: str = Field(..., description="The prerequisite task")


def check_dependency_cycle(tasks_deps: Dict[str, List[str]], task_id: str, dep_id: str) -> bool:
    """
    Checks if making task_id depend on dep_id creates a circular dependency.
    Returns True if a cycle would be created, False otherwise.
    """
    if task_id == dep_id:
        return True

    visited = set()
    stack = [dep_id]

    while stack:
        curr = stack.pop()
        if curr == task_id:
            return True
        if curr not in visited:
            visited.add(curr)
            for upstream in tasks_deps.get(curr, []):
                stack.append(upstream)

    return False


@router.get("/projects/{project_id}/dag")
async def get_project_dag(project_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns the authoritative DAG representation for visual canvas:
    nodes, edges, execution order, and topological validity.
    """
    res = await db.execute(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.created_at.asc())
    )
    tasks = res.scalars().all()

    nodes = []
    edges = []
    task_map: Dict[str, Task] = {t.id: t for t in tasks}
    deps_map: Dict[str, List[str]] = {}

    for t in tasks:
        deps = t.get_dependency_list()
        deps_map[t.id] = deps
        current_status = t.status.value if hasattr(t.status, "value") else str(t.status)
        nodes.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "task_type": t.task_type,
            "status": current_status,
            "priority": t.priority,
            "assigned_provider": t.assigned_provider,
            "assigned_model": t.assigned_model,
            "requires_approval": t.requires_approval,
            "approval_reason": t.approval_reason,
            "rejection_reason": t.rejection_reason,
            "dependencies": deps,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        })

        for dep_id in deps:
            if dep_id in task_map:
                edges.append({
                    "id": f"e-{dep_id}->{t.id}",
                    "source": dep_id,
                    "target": t.id,
                })

    # Compute topological sort execution order
    in_degree = {t.id: 0 for t in tasks}
    adj: Dict[str, List[str]] = {t.id: [] for t in tasks}
    for t in tasks:
        for d in deps_map.get(t.id, []):
            if d in adj:
                adj[d].append(t.id)
                in_degree[t.id] += 1

    queue = [t_id for t_id, deg in in_degree.items() if deg == 0]
    order = []
    while queue:
        curr = queue.pop(0)
        order.append(curr)
        for nxt in adj.get(curr, []):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    is_acyclic = (len(order) == len(tasks))

    return {
        "project_id": project_id,
        "nodes": nodes,
        "edges": edges,
        "execution_order": order,
        "is_acyclic": is_acyclic,
        "summary": {
            "total_tasks": len(tasks),
            "total_dependencies": len(edges),
            "pending": sum(1 for n in nodes if n["status"] == TaskStatus.PENDING.value),
            "awaiting_approval": sum(1 for n in nodes if n["status"] == TaskStatus.AWAITING_APPROVAL.value),
            "running": sum(1 for n in nodes if n["status"] == TaskStatus.RUNNING.value),
            "completed": sum(1 for n in nodes if n["status"] == TaskStatus.COMPLETED.value),
            "failed": sum(1 for n in nodes if n["status"] == TaskStatus.FAILED.value),
            "rejected": sum(1 for n in nodes if n["status"] == TaskStatus.REJECTED.value),
            "blocked": sum(1 for n in nodes if n["status"] == TaskStatus.BLOCKED.value),
        },
    }


@router.post("/projects/{project_id}/dependencies")
async def add_task_dependency(
    project_id: str,
    payload: DependencyModificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Add a dependency edge between two tasks in the project.
    Strictly prevents circular dependencies and invalid task associations.
    """
    if payload.task_id == payload.depends_on_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot depend on itself.",
        )

    # Verify both tasks exist in this project
    t1_res = await db.execute(
        select(Task).where(Task.id == payload.task_id, Task.project_id == project_id)
    )
    task1 = t1_res.scalar_one_or_none()
    if not task1:
        raise HTTPException(status_code=404, detail=f"Task {payload.task_id} not found in this project.")

    t2_res = await db.execute(
        select(Task).where(Task.id == payload.depends_on_task_id, Task.project_id == project_id)
    )
    task2 = t2_res.scalar_one_or_none()
    if not task2:
        raise HTTPException(status_code=404, detail=f"Prerequisite task {payload.depends_on_task_id} not found in this project.")

    existing_deps = task1.get_dependency_list()
    if payload.depends_on_task_id in existing_deps:
        return {"status": "already_exists", "message": "Dependency already exists."}

    # Fetch all tasks in project to verify DAG acyclicity
    p_tasks_res = await db.execute(select(Task).where(Task.project_id == project_id))
    all_tasks = p_tasks_res.scalars().all()
    tasks_deps = {t.id: t.get_dependency_list() for t in all_tasks}

    # Cycle check
    has_cycle = check_dependency_cycle(tasks_deps, payload.task_id, payload.depends_on_task_id)
    if has_cycle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Circular dependency rejected: Adding dependency '{task1.title}' -> '{task2.title}' "
                f"would create a cycle in the task graph."
            ),
        )

    # Persist in SQLite
    existing_deps.append(payload.depends_on_task_id)
    task1.dependencies = ",".join(existing_deps)
    await db.commit()

    # Link in FalkorDB (safely)
    try:
        memory_service.link_task_dependency(project_id, payload.task_id, payload.depends_on_task_id)
    except FalkorDBConnectionError:
        pass

    # Real-time WebSocket event
    await coordinator.emit_event(
        project_id,
        "dependency_added",
        {
            "task_id": payload.task_id,
            "depends_on_task_id": payload.depends_on_task_id,
        },
    )

    return {
        "status": "added",
        "task_id": payload.task_id,
        "depends_on_task_id": payload.depends_on_task_id,
        "dependencies": existing_deps,
    }


@router.delete("/projects/{project_id}/dependencies")
async def remove_task_dependency(
    project_id: str,
    payload: DependencyModificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Remove a dependency edge between two tasks."""
    t1_res = await db.execute(
        select(Task).where(Task.id == payload.task_id, Task.project_id == project_id)
    )
    task1 = t1_res.scalar_one_or_none()
    if not task1:
        raise HTTPException(status_code=404, detail="Task not found in this project.")

    existing_deps = task1.get_dependency_list()
    if payload.depends_on_task_id not in existing_deps:
        return {"status": "not_found", "message": "Dependency does not exist."}

    existing_deps.remove(payload.depends_on_task_id)
    task1.dependencies = ",".join(existing_deps) if existing_deps else None
    await db.commit()

    await coordinator.emit_event(
        project_id,
        "dependency_removed",
        {
            "task_id": payload.task_id,
            "depends_on_task_id": payload.depends_on_task_id,
        },
    )

    return {
        "status": "removed",
        "task_id": payload.task_id,
        "removed_dependency": payload.depends_on_task_id,
        "dependencies": existing_deps,
    }
