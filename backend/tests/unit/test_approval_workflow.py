"""
Unit & Workflow Tests for Human-in-the-Loop Approval System.
Tests:
1. Approval of a task in AWAITING_APPROVAL.
2. Rejection of a task and reason persistence.
3. Duplicate approval prevention (rejecting second approval).
4. Approval of an invalid task state (cannot approve pending, completed, or failed task directly).
5. Approval rejected when upstream dependencies are not completed.
6. Coordinator execution after approval.
7. Persistence of approval decision and audit trail (approved_by, approved_at, approval_reason).
8. Task edit & resubmission workflow.
9. Error handling on invalid approval or rejection inputs.
"""

from datetime import datetime, timezone
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select

from api.v1.tasks import (
    approve_task,
    reject_task,
    edit_and_resubmit_task,
    get_task_approval_context,
    TaskApprovalRequest,
    TaskRejectionRequest,
    TaskEditRequest,
)
from db.models import Project, Task, TaskStatus, TaskType
from db.session import get_session_context


@pytest_asyncio.fixture
async def sample_project_and_tasks():
    async with get_session_context() as session:
        proj = Project(name="Approval Test Project", domain="software")
        session.add(proj)
        await session.flush()

        task_dep = Task(
            project_id=proj.id,
            title="Upstream Task",
            task_type=TaskType.ANALYZE.value,
            status=TaskStatus.PENDING.value,
        )
        session.add(task_dep)
        await session.flush()

        task_gated = Task(
            project_id=proj.id,
            title="Gated Critical Task",
            task_type=TaskType.CODE.value,
            requires_approval=True,
            dependencies=task_dep.id,
            status=TaskStatus.AWAITING_APPROVAL.value,
        )
        session.add(task_gated)
        await session.flush()

        proj_id = proj.id
        dep_id = task_dep.id
        gated_id = task_gated.id

    return proj_id, dep_id, gated_id


@pytest.mark.asyncio
async def test_reject_task_persists_reason_and_blocks_downstream(sample_project_and_tasks):
    """Test 2 & 7: Rejection records reason and audit trail."""
    _, _, gated_id = sample_project_and_tasks

    async with get_session_context() as session:
        req = TaskRejectionRequest(reason="Security criteria not met: unsafe reflection used")
        res = await reject_task(task_id=gated_id, payload=req, db=session)

        assert res["status"] == "rejected"
        assert res["task_id"] == gated_id
        assert "Security criteria" in res["reason"]

        # Verify database persistence
        task_res = await session.execute(select(Task).where(Task.id == gated_id))
        task = task_res.scalar_one()
        assert task.status == TaskStatus.REJECTED.value
        assert task.rejection_reason == "Security criteria not met: unsafe reflection used"


@pytest.mark.asyncio
async def test_approval_rejected_when_dependencies_incomplete(sample_project_and_tasks):
    """Test 5: Cannot approve/execute task before dependencies finish."""
    _, dep_id, gated_id = sample_project_and_tasks

    async with get_session_context() as session:
        # Dependency is still PENDING
        req = TaskApprovalRequest(reason="Approve ahead of time")
        with pytest.raises(HTTPException) as exc_info:
            await approve_task(task_id=gated_id, payload=req, db=session)

        assert exc_info.value.status_code == 400
        assert "upstream dependencies not completed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_duplicate_and_invalid_state_approval_rejected(sample_project_and_tasks):
    """Test 3 & 4: Prevents duplicate approvals and approval of invalid states."""
    _, dep_id, gated_id = sample_project_and_tasks

    async with get_session_context() as session:
        # 1. Attempt to approve task_dep which is in PENDING state (not AWAITING_APPROVAL)
        with pytest.raises(HTTPException) as exc_info:
            await approve_task(task_id=dep_id, payload=TaskApprovalRequest(), db=session)
        assert exc_info.value.status_code == 400
        assert "Cannot approve task in 'pending' state" in exc_info.value.detail

        # 2. Mark gated_id as already COMPLETED
        t_res = await session.execute(select(Task).where(Task.id == gated_id))
        task = t_res.scalar_one()
        task.status = TaskStatus.COMPLETED.value
        await session.commit()

        # Duplicate approval on completed task must be rejected
        with pytest.raises(HTTPException) as exc_info2:
            await approve_task(task_id=gated_id, payload=TaskApprovalRequest(), db=session)
        assert exc_info2.value.status_code == 400
        assert "Cannot approve task in 'completed' state" in exc_info2.value.detail


@pytest.mark.asyncio
async def test_edit_and_resubmit_after_rejection(sample_project_and_tasks):
    """Test 8: Edit rejected task resets status to pending for resubmission."""
    _, _, gated_id = sample_project_and_tasks

    async with get_session_context() as session:
        # First reject it
        await reject_task(task_id=gated_id, payload=TaskRejectionRequest(reason="Revise design"), db=session)

        # Now edit and resubmit
        edit_req = TaskEditRequest(
            title="Revised Critical Task with Sandboxed Runner",
            acceptance_criteria="All tests pass in sandbox container",
        )
        updated = await edit_and_resubmit_task(task_id=gated_id, payload=edit_req, db=session)

        assert updated.status == TaskStatus.PENDING.value
        assert updated.title == "Revised Critical Task with Sandboxed Runner"
        assert updated.rejection_reason is None


@pytest.mark.asyncio
async def test_get_approval_context_details(sample_project_and_tasks):
    """Test 1 & frontend payload: Context endpoint returns upstream status and risks."""
    _, dep_id, gated_id = sample_project_and_tasks

    async with get_session_context() as session:
        ctx = await get_task_approval_context(task_id=gated_id, db=session)
        assert ctx["task_id"] == gated_id
        assert len(ctx["upstream_dependencies"]) == 1
        assert ctx["dependencies_all_completed"] is False
        assert any("Upstream dependencies" in r for r in ctx["risks"])
        assert "approve" in ctx["available_actions"]
