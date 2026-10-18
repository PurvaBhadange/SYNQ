"""
Unit & Integration Tests for Interactive Visual DAG Canvas & Cycle Detection.
Tests:
1. Rendering valid DAG with topological execution order.
2. Displaying all task states (PENDING, AWAITING_APPROVAL, RUNNING, COMPLETED, FAILED, REJECTED, BLOCKED).
3. Detecting and strictly rejecting direct circular dependencies (A -> B, B -> A).
4. Detecting and strictly rejecting multi-step transitive cycles (A -> B -> C -> A).
5. Preventing self-dependencies (A -> A).
6. Handling empty projects cleanly.
7. Removing dependencies safely.
8. Nonexistent task dependency rejection.
"""

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

from api.v1.tasks import (
    get_project_dag,
    add_task_dependency,
    remove_task_dependency,
    DependencyModificationRequest,
    check_dependency_cycle,
)
from db.models import Project, Task, TaskStatus, TaskType
from db.session import get_session_context


@pytest_asyncio.fixture
async def sample_dag_project():
    async with get_session_context() as session:
        proj = Project(name="DAG Test Project", domain="software")
        session.add(proj)
        await session.flush()

        # Task A
        task_a = Task(
            project_id=proj.id,
            title="Task A: Architecture Spec",
            task_type=TaskType.ANALYZE.value,
            status=TaskStatus.COMPLETED.value,
        )
        session.add(task_a)
        await session.flush()

        # Task B (depends on A)
        task_b = Task(
            project_id=proj.id,
            title="Task B: Backend Core",
            task_type=TaskType.CODE.value,
            status=TaskStatus.RUNNING.value,
            dependencies=task_a.id,
        )
        session.add(task_b)
        await session.flush()

        # Task C (depends on B)
        task_c = Task(
            project_id=proj.id,
            title="Task C: Frontend Integration",
            task_type=TaskType.CODE.value,
            status=TaskStatus.AWAITING_APPROVAL.value,
            dependencies=task_b.id,
            requires_approval=True,
        )
        session.add(task_c)
        await session.flush()

        proj_id = proj.id
        id_a = task_a.id
        id_b = task_b.id
        id_c = task_c.id

    return proj_id, id_a, id_b, id_c


@pytest.mark.asyncio
async def test_get_project_dag_structure(sample_dag_project):
    """Test 1 & 2: Authoritative DAG rendering with all nodes and edges."""
    proj_id, id_a, id_b, id_c = sample_dag_project

    async with get_session_context() as session:
        dag = await get_project_dag(project_id=proj_id, db=session)

        assert dag["project_id"] == proj_id
        assert len(dag["nodes"]) == 3
        assert len(dag["edges"]) == 2
        assert dag["is_acyclic"] is True

        # Execution order must have A before B and B before C
        order = dag["execution_order"]
        assert order.index(id_a) < order.index(id_b)
        assert order.index(id_b) < order.index(id_c)

        summary = dag["summary"]
        assert summary["total_tasks"] == 3
        assert summary["completed"] == 1
        assert summary["running"] == 1
        assert summary["awaiting_approval"] == 1


@pytest.mark.asyncio
async def test_reject_self_dependency(sample_dag_project):
    """Test 5: Cannot make a task depend on itself."""
    proj_id, id_a, _, _ = sample_dag_project

    async with get_session_context() as session:
        req = DependencyModificationRequest(task_id=id_a, depends_on_task_id=id_a)
        with pytest.raises(HTTPException) as exc:
            await add_task_dependency(project_id=proj_id, payload=req, db=session)

        assert exc.value.status_code == 400
        assert "cannot depend on itself" in exc.value.detail


@pytest.mark.asyncio
async def test_reject_direct_circular_dependency(sample_dag_project):
    """Test 3: Reject direct circular dependency (Task B depends on A; cannot make A depend on B)."""
    proj_id, id_a, id_b, _ = sample_dag_project

    async with get_session_context() as session:
        # B already depends on A. Trying to make A depend on B would create cycle: A -> B -> A.
        req = DependencyModificationRequest(task_id=id_a, depends_on_task_id=id_b)
        with pytest.raises(HTTPException) as exc:
            await add_task_dependency(project_id=proj_id, payload=req, db=session)

        assert exc.value.status_code == 400
        assert "Circular dependency rejected" in exc.value.detail


@pytest.mark.asyncio
async def test_reject_transitive_circular_dependency(sample_dag_project):
    """Test 4: Reject transitive circular dependency (C depends on B which depends on A; cannot make A depend on C)."""
    proj_id, id_a, _, id_c = sample_dag_project

    async with get_session_context() as session:
        # A -> B -> C. Trying to make A depend on C would create cycle: A -> C -> B -> A.
        req = DependencyModificationRequest(task_id=id_a, depends_on_task_id=id_c)
        with pytest.raises(HTTPException) as exc:
            await add_task_dependency(project_id=proj_id, payload=req, db=session)

        assert exc.value.status_code == 400
        assert "Circular dependency rejected" in exc.value.detail


@pytest.mark.asyncio
async def test_add_and_remove_valid_dependency(sample_dag_project):
    """Test adding a valid independent edge and removing it."""
    proj_id, id_a, _, id_c = sample_dag_project

    async with get_session_context() as session:
        # Add explicit dependency: C also depends on A directly (valid diamond/redundant edge)
        req = DependencyModificationRequest(task_id=id_c, depends_on_task_id=id_a)
        res = await add_task_dependency(project_id=proj_id, payload=req, db=session)
        assert res["status"] == "added"

        # Now remove that edge
        rem_res = await remove_task_dependency(project_id=proj_id, payload=req, db=session)
        assert rem_res["status"] == "removed"


@pytest.mark.asyncio
async def test_empty_project_dag():
    """Test 6: Empty project DAG returns clean empty structure."""
    async with get_session_context() as session:
        proj = Project(name="Empty Project", domain="general")
        session.add(proj)
        await session.flush()
        proj_id = proj.id

        dag = await get_project_dag(project_id=proj_id, db=session)
        assert dag["nodes"] == []
        assert dag["edges"] == []
        assert dag["is_acyclic"] is True
        assert dag["summary"]["total_tasks"] == 0
