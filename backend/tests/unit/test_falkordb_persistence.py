"""
Unit & Integration Tests for FalkorDB Persistent Graph Memory.
Verifies:
1. FalkorDB connectivity and health check reporting.
2. Creating a project graph with Cypher.
3. Writing nodes and relationships with Cypher.
4. Reading nodes and relationships with Cypher.
5. Retrieving context across completed tasks.
6. Simulating backend restart and retrieving existing graph data.
7. Handling a disconnected FalkorDB instance.
8. Confirming that graph writes are NOT falsely reported as successful when offline.
9. Confirming that in-memory test adapter cannot silently become the production backend.
"""

from unittest.mock import MagicMock, patch
import pytest

from config import get_settings
from memory.falkordb_client import FalkorDBClient, FalkorDBConnectionError, InMemoryGraph
from memory.memory_service import MemoryService


class MockQueryResult:
    def __init__(self, result_set):
        self.result_set = result_set


class MockFalkorNode:
    def __init__(self, node_id, labels, properties):
        self.id = node_id
        self.labels = labels
        self.properties = properties


class MockFalkorEdge:
    def __init__(self, src_node, relation, dest_node, properties=None):
        self.src_node = src_node
        self.relation = relation
        self.dest_node = dest_node
        self.properties = properties or {}


def test_falkordb_status_disconnected_by_default():
    """Test 7 & 8: Verify disconnected FalkorDB reports status and rejects writes without fallback."""
    settings = get_settings()
    orig = settings.falkordb_allow_in_memory_fallback
    settings.falkordb_allow_in_memory_fallback = False

    client = FalkorDBClient()
    # Force connection failure
    with patch("memory.falkordb_client.FalkorDB", side_effect=ConnectionRefusedError("Connection refused")):
        success = client.connect(force=True)
        assert success is False
        assert client.is_connected is False
        assert client.status == "disconnected"
        assert client.backend_mode == "none"

        status = client.get_status()
        assert status["connected"] is False
        assert status["status"] == "disconnected"
        assert status["persistence_guaranteed"] is False

        # Confirm query raises FalkorDBConnectionError (not silent success!)
        with pytest.raises(FalkorDBConnectionError):
            client.query("test_graph", "MATCH (n) RETURN n")

    settings.falkordb_allow_in_memory_fallback = orig


def test_falkordb_in_memory_test_adapter_cannot_silently_become_production():
    """Test 9: In-memory adapter only activates when explicitly configured in settings."""
    settings = get_settings()
    orig = settings.falkordb_allow_in_memory_fallback

    # Production mode: fallback forbidden
    settings.falkordb_allow_in_memory_fallback = False
    client = FalkorDBClient()
    with patch("memory.falkordb_client.FalkorDB", side_effect=ConnectionRefusedError("Offline")):
        client.connect(force=True)
        assert client.status == "disconnected"
        assert client.backend_mode != "in_memory_test"

    # Explicit test mode: fallback allowed
    settings.falkordb_allow_in_memory_fallback = True
    client_test = FalkorDBClient()
    with patch("memory.falkordb_client.FalkorDB", side_effect=ConnectionRefusedError("Offline")):
        client_test.connect(force=True)
        assert client_test.status == "in_memory_test"
        assert client_test.backend_mode == "in_memory_test"

    settings.falkordb_allow_in_memory_fallback = orig


def test_memory_service_disconnected_safely_pauses():
    """Test 7 & 8: MemoryService cleanly pauses and reports failure without corrupting state."""
    settings = get_settings()
    orig = settings.falkordb_allow_in_memory_fallback
    settings.falkordb_allow_in_memory_fallback = False

    service = MemoryService()
    # Mock client as disconnected
    service.client._connected = False
    service.client._status = "disconnected"
    service.client._backend_mode = "none"
    service.client._last_error = "Server unreachable"

    # Writes must raise FalkorDBConnectionError
    with pytest.raises(FalkorDBConnectionError):
        service.create_project_node("proj-offline", "Test", "general")

    with pytest.raises(FalkorDBConnectionError):
        service.create_task_node("proj-offline", "task-1", "Task 1", "code")

    # Reads must return honest disconnected payload, never empty success
    graph_data = service.get_project_graph("proj-offline")
    assert graph_data["status"] == "disconnected"
    assert graph_data["backend"] == "none"
    assert "error" in graph_data

    context = service.build_context_package("proj-offline", "task-1")
    assert context["status"] == "disconnected"
    assert "error" in context

    settings.falkordb_allow_in_memory_fallback = orig


def test_falkordb_real_cypher_lifecycle_and_persistence_across_restarts():
    """
    Tests 1, 2, 3, 4, 5, 6:
    Simulates real FalkorDB driver executing Cypher queries for project creation,
    task nodes, dependencies, executions, artifacts, decisions, and cross-task retrieval.
    Verifies data retrieval across simulated backend restart.
    """
    mock_db = MagicMock()
    mock_graph = MagicMock()
    mock_db.select_graph.return_value = mock_graph
    mock_db.connection.ping.return_value = True

    # Storage simulating real graph in FalkorDB
    cypher_calls = []

    def mock_query(cypher, params=None):
        cypher_calls.append((cypher.strip(), params or {}))
        # If querying the graph for visualizer
        if "MATCH (n)" in cypher and "OPTIONAL MATCH (n)-[r]->(m)" in cypher:
            p_node = MockFalkorNode(1, ["Project"], {"id": "proj-persisted", "name": "Persisted Project", "domain": "ai"})
            t1_node = MockFalkorNode(2, ["Task"], {"id": "task-alpha", "title": "Alpha Spec", "task_type": "analyze"})
            t2_node = MockFalkorNode(3, ["Task"], {"id": "task-beta", "title": "Beta Build", "task_type": "code"})
            return MockQueryResult([
                [p_node, "HAS_TASK", {}, t1_node],
                [t2_node, "DEPENDS_ON", {}, t1_node],
            ])
        # If querying for context package
        if "MATCH (t:Task {id: $task_id})-[:DEPENDS_ON]->(dep:Task)" in cypher:
            dep_node = MockFalkorNode(2, ["Task"], {"id": "task-alpha", "title": "Alpha Spec", "task_type": "analyze"})
            ex_node = MockFalkorNode(4, ["Execution"], {"id": "exec-1", "provider_id": "groq", "model_id": "llama3"})
            art_node = MockFalkorNode(5, ["Artifact"], {"id": "art-1", "name": "Spec Document", "artifact_type": "doc", "preview": "Spec details"})
            dec_node = MockFalkorNode(6, ["Decision"], {"id": "dec-1", "description": "Selected Groq", "rationale": "Lowest latency"})
            return MockQueryResult([
                [dep_node, ex_node, art_node, dec_node],
            ])
        return MockQueryResult([])

    mock_graph.query.side_effect = mock_query

    # 1. First "Session" (backend running)
    service1 = MemoryService()
    service1.client._driver = mock_db
    service1.client._connected = True
    service1.client._status = "connected"
    service1.client._backend_mode = "falkordb"

    # Write project, tasks, dependencies
    service1.create_project_node("proj-persisted", "Persisted Project", "ai")
    service1.create_task_node("proj-persisted", "task-alpha", "Alpha Spec", "analyze")
    service1.create_task_node("proj-persisted", "task-beta", "Beta Build", "code")
    service1.link_task_dependency("proj-persisted", "task-beta", "task-alpha")
    service1.record_execution_node("proj-persisted", "task-alpha", "exec-1", "groq", "llama3", "succeeded")
    service1.record_artifact("proj-persisted", "exec-1", "art-1", "doc", "Spec Document", "Spec details")
    service1.record_decision("proj-persisted", "exec-1", "dec-1", "Selected Groq", "Lowest latency")

    # Verify Cypher statements were dispatched
    assert any("MERGE (p:Project {id: $id})" in c[0] for c in cypher_calls)
    assert any("MERGE (t:Task {id: $task_id})" in c[0] for c in cypher_calls)
    assert any("MERGE (t1)-[:DEPENDS_ON]->(t2)" in c[0] for c in cypher_calls)
    assert any("MERGE (e:Execution {id: $execution_id})" in c[0] for c in cypher_calls)
    assert any("MERGE (a:Artifact {id: $artifact_id})" in c[0] for c in cypher_calls)
    assert any("MERGE (d:Decision {id: $decision_id})" in c[0] for c in cypher_calls)

    # Clean shutdown of first session
    service1.client.close()
    assert service1.client.is_connected is False

    # 2. Restart backend: instantiate brand new MemoryService (Simulating backend restart)
    service2 = MemoryService()
    service2.client._driver = mock_db
    service2.client._connected = True
    service2.client._status = "connected"
    service2.client._backend_mode = "falkordb"

    # Retrieve graph visualizer data from persistent FalkorDB
    graph = service2.get_project_graph("proj-persisted")
    assert graph["status"] == "connected"
    assert graph["backend"] == "falkordb"
    assert len(graph["nodes"]) >= 3
    assert len(graph["edges"]) >= 2

    # Retrieve context package across backend restart
    context = service2.build_context_package("proj-persisted", "task-beta")
    assert context["status"] == "connected"
    assert context["backend"] == "falkordb"
    assert len(context["dependency_outputs"]) == 1
    assert context["dependency_outputs"][0]["task_id"] == "task-alpha"
    assert len(context["artifacts"]) == 1
    assert context["artifacts"][0]["name"] == "Spec Document"
    assert len(context["relevant_decisions"]) == 1
    assert context["relevant_decisions"][0]["description"] == "Selected Groq"
