"""
Unit tests for Task Planner.
Tests deterministic decomposition fallback, DAG topological sorting, and cycle detection.
"""

import pytest
from core.planner import Planner, TaskProposal


@pytest.mark.asyncio
async def test_deterministic_planner_software():
    planner = Planner()
    res = await planner.plan("Build a REST API with FastAPI and SQLite", domain="software")

    assert res.is_dag_valid
    assert len(res.tasks) >= 3
    assert res.planner_type == "deterministic_fallback"
    # Ensure task indices match topological order
    assert res.execution_order[0] == 0


@pytest.mark.asyncio
async def test_deterministic_planner_research():
    planner = Planner()
    res = await planner.plan("Investigate vector indexing vs graph databases for LLM memory", domain="research")

    assert res.is_dag_valid
    assert any(t.task_type == "research" for t in res.tasks)


def test_topological_sort_acyclic():
    planner = Planner()
    tasks = [
        TaskProposal(index=0, title="T0", description="", task_type="general", priority=5, dependencies=[]),
        TaskProposal(index=1, title="T1", description="", task_type="general", priority=5, dependencies=[0]),
        TaskProposal(index=2, title="T2", description="", task_type="general", priority=5, dependencies=[1]),
    ]
    order, is_valid = planner._topological_sort(tasks)
    assert is_valid
    assert order == [0, 1, 2]


def test_topological_sort_cycle():
    planner = Planner()
    # Circular dependency: 0 -> 1 -> 0
    tasks = [
        TaskProposal(index=0, title="T0", description="", task_type="general", priority=5, dependencies=[1]),
        TaskProposal(index=1, title="T1", description="", task_type="general", priority=5, dependencies=[0]),
    ]
    order, is_valid = planner._topological_sort(tasks)
    assert not is_valid
