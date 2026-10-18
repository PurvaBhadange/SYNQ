"""
Integration tests for Task Coordinator execution flow and fallback recovery.
Uses in-memory SQLite and mock providers to test end-to-end orchestration without real API keys.
"""

import uuid
import pytest
from core.capability_registry import CapabilityRegistry
from core.coordinator import TaskCoordinator
from core.router import HealthTracker, Router
from core.validator import OutputValidator
from db.models import Base, Project, Task, TaskStatus, TaskExecution, RoutingDecision
from db.session import get_session_context, init_db
from memory.memory_service import MemoryService
from tests.mocks.mock_provider import MockProvider
from sqlalchemy import select


@pytest.fixture
async def setup_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_coordinator_execution_success(setup_db):
    # Setup test registry with a mock code provider
    reg = CapabilityRegistry()
    mock_p = MockProvider(
        provider_id="mock-ollama",
        model_id="qwen-coder",
        response_content="def solve():\n    return 42\n",
        supported_task_types=["code", "general"],
        is_local=True,
    )
    reg.register_provider(mock_p)

    health = HealthTracker()
    router = Router(registry=reg, health=health)
    val = OutputValidator()
    mem = MemoryService()
    coord = TaskCoordinator(router=router, validator=val, memory=mem, registry=reg)

    # 1. Create project and task
    project_id = f"proj-{uuid.uuid4()}"
    task_id = f"task-{uuid.uuid4()}"

    async with get_session_context() as session:
        proj = Project(id=project_id, name="Coord Test Proj", domain="software")
        session.add(proj)
        task = Task(
            id=task_id,
            project_id=project_id,
            title="Write solver function",
            task_type="code",
            priority=8,
            acceptance_criteria="Must return 42",
        )
        session.add(task)
        await session.commit()

    # 2. Execute task through coordinator
    res = await coord.execute_task(task_id)

    assert res["status"] == "succeeded"
    assert res["provider_id"] == "mock-ollama"
    assert "def solve():" in res["output"]

    # 3. Verify SQLite DB updated
    async with get_session_context() as session:
        t_res = await session.execute(select(Task).where(Task.id == task_id))
        t = t_res.scalar_one()
        assert t.status == TaskStatus.COMPLETED.value
        assert t.assigned_provider == "mock-ollama"

        ex_res = await session.execute(select(TaskExecution).where(TaskExecution.task_id == task_id))
        executions = ex_res.scalars().all()
        assert len(executions) == 1
        assert executions[0].status == "succeeded"
        assert executions[0].validation_passed is True

        rd_res = await session.execute(select(RoutingDecision).where(RoutingDecision.task_id == task_id))
        rd = rd_res.scalar_one()
        assert rd.selected_provider == "mock-ollama"


@pytest.mark.asyncio
async def test_coordinator_fallback_on_failure(setup_db):
    reg = CapabilityRegistry()
    # Primary provider that will fail
    failing_p = MockProvider(
        provider_id="failing-provider",
        model_id="fail-model",
        fail_execution_only=True,
        supported_task_types=["write", "general"],
        is_local=True,
    )
    # Secondary backup provider that succeeds
    backup_p = MockProvider(
        provider_id="backup-provider",
        model_id="backup-model",
        should_fail=False,
        response_content=(
            "# Project Summary Report\n\n"
            "This is a comprehensive summary report written by the backup provider. "
            "It outlines project milestones, execution details, and future recommendations."
        ),
        supported_task_types=["write", "general"],
        is_local=False,
    )
    reg.register_provider(failing_p)
    reg.register_provider(backup_p)

    health = HealthTracker()
    router = Router(registry=reg, health=health)
    val = OutputValidator()
    mem = MemoryService()
    coord = TaskCoordinator(router=router, validator=val, memory=mem, registry=reg)

    project_id = f"proj-fb-{uuid.uuid4()}"
    task_id = f"task-fb-{uuid.uuid4()}"

    async with get_session_context() as session:
        proj = Project(id=project_id, name="Fallback Test Proj", domain="general")
        session.add(proj)
        task = Task(
            id=task_id,
            project_id=project_id,
            title="Write summary report",
            task_type="write",
            priority=5,
        )
        session.add(task)
        await session.commit()

    # Execute task — should automatically fallback to backup provider
    res = await coord.execute_task(task_id)

    assert res["status"] == "succeeded"
    assert res["provider_id"] == "backup-provider"

    # Verify failing provider was degraded
    assert health.is_degraded("failing-provider", "fail-model")


@pytest.mark.asyncio
async def test_coordinator_fallback_on_validation_failure(setup_db):
    """
    Verifies that when an attempt fails validation, the coordinator successfully
    falls back to the next candidate without primary key collision on execution_id.
    """
    reg = CapabilityRegistry()
    # Primary provider that returns bad syntax
    invalid_code_p = MockProvider(
        provider_id="bad-code-provider",
        model_id="bad-model",
        response_content="def broken_syntax(\n    return 0",
        supported_task_types=["code", "general"],
        is_local=True,
    )
    # Secondary provider that returns clean code
    clean_code_p = MockProvider(
        provider_id="clean-code-provider",
        model_id="clean-model",
        response_content="def working_syntax():\n    return 42\n",
        supported_task_types=["code", "general"],
        is_local=False,
    )
    reg.register_provider(invalid_code_p)
    reg.register_provider(clean_code_p)

    health = HealthTracker()
    router = Router(registry=reg, health=health)
    val = OutputValidator()
    mem = MemoryService()
    coord = TaskCoordinator(router=router, validator=val, memory=mem, registry=reg)

    project_id = f"proj-val-fb-{uuid.uuid4()}"
    task_id = f"task-val-fb-{uuid.uuid4()}"

    async with get_session_context() as session:
        proj = Project(id=project_id, name="Val FB Proj", domain="software")
        session.add(proj)
        task = Task(
            id=task_id,
            project_id=project_id,
            title="Write valid code",
            task_type="code",
            priority=8,
        )
        session.add(task)
        await session.commit()

    res = await coord.execute_task(task_id)
    assert res["status"] == "succeeded"
    assert res["provider_id"] == "clean-code-provider"

    # Check both executions were persisted with unique IDs
    async with get_session_context() as session:
        ex_res = await session.execute(
            select(TaskExecution).where(TaskExecution.task_id == task_id).order_by(TaskExecution.attempt_number)
        )
        executions = ex_res.scalars().all()
        assert len(executions) == 2
        assert executions[0].attempt_number == 1
        assert executions[0].status == "failed"
        assert executions[0].validation_passed is False
        assert executions[1].attempt_number == 2
        assert executions[1].status == "succeeded"
        assert executions[1].validation_passed is True
        assert executions[0].id != executions[1].id

