"""
FalkorDB Client
Handles connection and Cypher query execution for SYNQ graph memory.
Includes an explicit in-memory graph adapter restricted to automated testing.
In production/normal mode, disallows silent in-memory substitution when FalkorDB is offline.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from config import get_settings

logger = logging.getLogger(__name__)

try:
    from falkordb import FalkorDB
    HAS_FALKORDB_LIB = True
except ImportError:
    HAS_FALKORDB_LIB = False
    FalkorDB = None


class FalkorDBConnectionError(RuntimeError):
    """Raised when FalkorDB is required but unreachable and fallback is disabled."""
    pass


class InMemoryGraph:
    """
    Explicit in-memory graph store for automated testing and isolated offline tests.
    Stores nodes and directed relationships in memory.
    """

    def __init__(self, name: str):
        self.name = name
        # id -> { "labels": [...], "properties": {...} }
        self.nodes: Dict[str, Dict[str, Any]] = {}
        # list of { "start": id, "end": id, "type": str, "properties": {...} }
        self.edges: List[Dict[str, Any]] = []

    def add_node(self, node_id: str, label: str, properties: Dict[str, Any]) -> None:
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "properties": {**properties, "id": node_id},
        }

    def add_edge(
        self, start_id: str, end_id: str, edge_type: str, properties: Optional[Dict[str, Any]] = None
    ) -> None:
        self.edges.append({
            "start": start_id,
            "end": end_id,
            "type": edge_type,
            "properties": properties or {},
        })

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_id)

    def get_related(
        self, node_id: str, edge_type: Optional[str] = None, direction: str = "out"
    ) -> List[Dict[str, Any]]:
        results = []
        for edge in self.edges:
            if edge_type and edge["type"] != edge_type:
                continue
            if direction in ("out", "both") and edge["start"] == node_id:
                target_node = self.nodes.get(edge["end"])
                if target_node:
                    results.append({
                        "node": target_node,
                        "edge": edge,
                        "direction": "out",
                    })
            if direction in ("in", "both") and edge["end"] == node_id:
                source_node = self.nodes.get(edge["start"])
                if source_node:
                    results.append({
                        "node": source_node,
                        "edge": edge,
                        "direction": "in",
                    })
        return results

    def to_graph_data(self) -> Dict[str, Any]:
        """Format nodes and links for frontend visualizers (D3, React Flow, etc.)."""
        nodes_list = [
            {
                "id": n["id"],
                "label": n["label"],
                **n["properties"],
            }
            for n in self.nodes.values()
        ]
        links_list = [
            {
                "source": e["start"],
                "target": e["end"],
                "type": e["type"],
                **e["properties"],
            }
            for e in self.edges
        ]
        return {"nodes": nodes_list, "edges": links_list}


class FalkorDBClient:
    """
    Client managing connections to FalkorDB.
    In production mode, reports actual connection failure without silent fallback.
    """

    def __init__(self):
        self.settings = get_settings()
        self._driver: Optional[Any] = None
        self._connected: bool = False
        self._status: str = "disconnected"  # "connected", "disconnected", "in_memory_test", "disabled"
        self._backend_mode: str = "none"    # "falkordb", "in_memory_test", "none"
        self._last_error: Optional[str] = None
        self._memory_graphs: Dict[str, InMemoryGraph] = {}
        self._last_connect_attempt: float = 0.0
        self._connect_cooldown: float = 3.0

    def connect(self, force: bool = False) -> bool:
        """Attempt to connect to FalkorDB Redis service."""
        if not self.settings.falkordb_enabled:
            self._status = "disabled"
            self._backend_mode = "none"
            self._connected = False
            return False

        if not HAS_FALKORDB_LIB or FalkorDB is None:
            self._connected = False
            self._last_error = "falkordb python package is not installed"
            if self.settings.falkordb_allow_in_memory_fallback:
                self._status = "in_memory_test"
                self._backend_mode = "in_memory_test"
                logger.info("FalkorDB library unavailable. Operating in explicit IN-MEMORY TEST mode.")
            else:
                self._status = "disconnected"
                self._backend_mode = "none"
                logger.error("FalkorDB library unavailable and fallback is disabled.")
            return False

        now = time.time()
        if not force and (now - self._last_connect_attempt < self._connect_cooldown):
            return self._connected

        self._last_connect_attempt = now
        host = self.settings.falkordb_host or "localhost"
        port = self.settings.falkordb_port or 6379

        try:
            db = FalkorDB(
                host=host,
                port=port,
                password=self.settings.falkordb_password,
                socket_connect_timeout=0.5,
                socket_timeout=1.0,
            )
            db.connection.ping()
            self._driver = db
            self._connected = True
            self._status = "connected"
            self._backend_mode = "falkordb"
            self._last_error = None
            logger.info("Connected successfully to FalkorDB at %s:%s", host, port)
            return True
        except Exception as exc:
            self._connected = False
            self._driver = None
            self._last_error = str(exc)

            if self.settings.falkordb_allow_in_memory_fallback:
                self._status = "in_memory_test"
                self._backend_mode = "in_memory_test"
                logger.warning(
                    "FalkorDB connection failed (%s). Operating in explicit IN-MEMORY TEST adapter mode.",
                    exc,
                )
            else:
                self._status = "disconnected"
                self._backend_mode = "none"
                logger.warning(
                    "FalkorDB connection failed (%s). Disconnected: graph operations will be paused.",
                    exc,
                )
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def status(self) -> str:
        return self._status

    @property
    def backend_mode(self) -> str:
        return self._backend_mode

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def get_status(self) -> Dict[str, Any]:
        """Detailed status dictionary for health check and API responses."""
        return {
            "status": self._status,
            "connected": self._connected,
            "backend": self._backend_mode,
            "host": self.settings.falkordb_host,
            "port": self.settings.falkordb_port,
            "error": self._last_error,
            "allow_in_memory_fallback": self.settings.falkordb_allow_in_memory_fallback,
            "persistence_guaranteed": self._connected and (self._backend_mode == "falkordb"),
        }

    def get_or_create_memory_graph(self, graph_name: str) -> InMemoryGraph:
        """Available only in explicit in_memory_test mode."""
        if graph_name not in self._memory_graphs:
            self._memory_graphs[graph_name] = InMemoryGraph(graph_name)
        return self._memory_graphs[graph_name]

    def query(self, graph_name: str, cypher: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a Cypher query on FalkorDB if connected.
        If in test adapter mode, logs and skips raw Cypher.
        If disconnected and fallback is disabled, raises FalkorDBConnectionError.
        """
        if self._connected and self._driver:
            try:
                graph = self._driver.select_graph(graph_name)
                return graph.query(cypher, params or {})
            except Exception as exc:
                logger.error("FalkorDB query failed on graph %s: %s", graph_name, exc)
                raise FalkorDBConnectionError(f"FalkorDB query failed: {exc}") from exc

        if self._status == "in_memory_test":
            logger.debug("In-memory test mode: raw Cypher query bypassed for %s", graph_name)
            return None

        raise FalkorDBConnectionError(
            f"FalkorDB is disconnected ({self._last_error or 'server unreachable'}). "
            f"Graph operations are paused."
        )

    def close(self) -> None:
        """Close FalkorDB driver connection cleanly."""
        try:
            if self._driver and hasattr(self._driver, "connection"):
                self._driver.connection.close()
        except Exception as exc:
            logger.debug("Error closing FalkorDB connection: %s", exc)
        finally:
            self._driver = None
            self._connected = False
            self._status = "disconnected"

    def reset_test_state(self) -> None:
        """Reset internal in-memory test graphs (used in tests)."""
        self._memory_graphs.clear()


# Global client instance
falkor_client = FalkorDBClient()
