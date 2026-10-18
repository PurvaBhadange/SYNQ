"""
Unit tests for Memory Service (In-Memory Test Adapter).
Tests node and edge creation, context package construction, and graph export in test mode.
"""

from unittest.mock import patch
import pytest
from config import get_settings
from memory.memory_service import MemoryService
from memory.falkordb_client import falkor_client


@pytest.fixture(autouse=True)
def setup_test_memory():
    settings = get_settings()
    orig = settings.falkordb_allow_in_memory_fallback
    settings.falkordb_allow_in_memory_fallback = True
    falkor_client.reset_test_state()
    with patch("memory.falkordb_client.FalkorDB", side_effect=ConnectionRefusedError("Offline")):
        falkor_client.connect(force=True)
        yield
    settings.falkordb_allow_in_memory_fallback = orig
    falkor_client.reset_test_state()


def test_memory_service_lifecycle():
    service = MemoryService()
    project_id = "test-proj-123"
    task_1_id = "task-1"
    task_2_id = "task-2"
    exec_1_id = "exec-1"

    # Status check confirms in-memory test adapter is clearly identified
    status = service.get_status()
    assert status["backend"] in ("in_memory_test", "falkordb")

    # Create project and tasks
    service.create_project_node(project_id, "Test Project", "software")
    service.create_task_node(project_id, task_1_id, "Write Architecture Spec", "analyze")
    service.create_task_node(project_id, task_2_id, "Implement Code", "code")
    service.link_task_dependency(project_id, task_2_id, task_1_id)

    # Record execution and artifact for task 1
    service.record_execution_node(
        project_id, task_1_id, exec_1_id, "ollama", "llama3.2", "succeeded"
    )
    service.record_artifact(
        project_id,
        exec_1_id,
        "art-1",
        "analyze",
        "Architecture Document",
        "System uses SQLite and FalkorDB graph memory.",
    )
    service.record_decision(
        project_id,
        exec_1_id,
        "dec-1",
        "Use FalkorDB for Graph Memory",
        "FalkorDB supports fast Cypher queries and continuous knowledge graphs.",
    )

    # Build context package for task 2 (which depends on task 1)
    context = service.build_context_package(project_id, task_2_id)
    assert context["task_id"] == task_2_id
    assert len(context["artifacts"]) >= 1
    assert context["artifacts"][0]["name"] == "Architecture Document"
    assert len(context["relevant_decisions"]) >= 1
    assert context["relevant_decisions"][0]["description"] == "Use FalkorDB for Graph Memory"

    # Check graph visualizer export
    graph_data = service.get_project_graph(project_id)
    assert len(graph_data["nodes"]) >= 5
    assert len(graph_data["edges"]) >= 4
    assert graph_data["backend"] in ("in_memory_test", "falkordb")
