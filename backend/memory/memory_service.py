"""
Memory Service — FalkorDB Project Memory & Knowledge Lineage for SYNQ.

Provides continuous, shared project memory across AI agents:
- Creates and updates Project, Task, Execution, Artifact, and Decision graph nodes.
- Manages graph relationships: HAS_TASK, DEPENDS_ON, EXECUTED_BY, PRODUCED, MADE_DECISION.
- Builds structured Context Packages for downstream tasks to prevent amnesia.
- Exports graph snapshots formatted for frontend visualization (D3 / React Flow).
- Enforces real FalkorDB persistence with explicit disconnected status handling.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from memory.falkordb_client import falkor_client, FalkorDBConnectionError, InMemoryGraph

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service managing persistent project memory in FalkorDB.
    Strictly reports connection state; supports explicit test adapter for unit tests.
    """

    def __init__(self):
        self.client = falkor_client

    def _get_graph_name(self, project_id: str) -> str:
        return f"synq_proj_{project_id.replace('-', '_')}"

    def ensure_connected(self) -> None:
        """Attempt connection if not already connected."""
        if not self.client.is_connected:
            self.client.connect()

    def get_status(self) -> Dict[str, Any]:
        """Return current status of FalkorDB graph persistence."""
        self.ensure_connected()
        return self.client.get_status()

    # ── Project & Task Graph Operations ──────────────────────────────────────────

    def create_project_node(self, project_id: str, name: str, domain: str) -> None:
        """Create or merge a Project node in FalkorDB."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        if self.client.is_connected:
            cypher = (
                "MERGE (p:Project {id: $id}) "
                "SET p.name = $name, p.domain = $domain, p.updated_at = timestamp()"
            )
            self.client.query(graph_name, cypher, {"id": project_id, "name": name, "domain": domain})
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_node(
                project_id,
                "Project",
                {"name": name, "domain": domain, "created_at": time.time()},
            )
            return

        raise FalkorDBConnectionError(
            f"Cannot write Project node: FalkorDB is disconnected ({self.client.last_error})."
        )

    def create_task_node(
        self, project_id: str, task_id: str, title: str, task_type: str, priority: int = 5
    ) -> None:
        """Create or merge a Task node and link to Project."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        if self.client.is_connected:
            cypher = (
                "MERGE (t:Task {id: $task_id}) "
                "SET t.title = $title, t.task_type = $task_type, t.priority = $priority, t.updated_at = timestamp() "
                "WITH t "
                "MATCH (p:Project {id: $project_id}) "
                "MERGE (p)-[:HAS_TASK]->(t)"
            )
            self.client.query(
                graph_name,
                cypher,
                {
                    "task_id": task_id,
                    "project_id": project_id,
                    "title": title,
                    "task_type": task_type,
                    "priority": priority,
                },
            )
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_node(
                task_id,
                "Task",
                {"title": title, "task_type": task_type, "priority": priority, "created_at": time.time()},
            )
            mem_graph.add_edge(project_id, task_id, "HAS_TASK")
            return

        raise FalkorDBConnectionError(
            f"Cannot write Task node: FalkorDB is disconnected ({self.client.last_error})."
        )

    def link_task_dependency(self, project_id: str, task_id: str, depends_on_task_id: str) -> None:
        """Record that task_id DEPENDS_ON depends_on_task_id."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        if self.client.is_connected:
            cypher = (
                "MATCH (t1:Task {id: $task_id}), (t2:Task {id: $depends_on_task_id}) "
                "MERGE (t1)-[:DEPENDS_ON]->(t2)"
            )
            self.client.query(graph_name, cypher, {"task_id": task_id, "depends_on_task_id": depends_on_task_id})
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_edge(task_id, depends_on_task_id, "DEPENDS_ON")
            return

        raise FalkorDBConnectionError(
            f"Cannot link Task dependency: FalkorDB is disconnected ({self.client.last_error})."
        )

    def record_execution_node(
        self,
        project_id: str,
        task_id: str,
        execution_id: str,
        provider_id: str,
        model_id: str,
        status: str,
    ) -> None:
        """Record execution details and link to Task."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        if self.client.is_connected:
            cypher = (
                "MATCH (t:Task {id: $task_id}) "
                "MERGE (e:Execution {id: $execution_id}) "
                "SET e.provider_id = $provider_id, e.model_id = $model_id, e.status = $status, e.started_at = timestamp() "
                "MERGE (t)-[:EXECUTED_BY]->(e)"
            )
            self.client.query(
                graph_name,
                cypher,
                {
                    "task_id": task_id,
                    "execution_id": execution_id,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "status": status,
                },
            )
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_node(
                execution_id,
                "Execution",
                {
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "status": status,
                    "started_at": time.time(),
                },
            )
            mem_graph.add_edge(task_id, execution_id, "EXECUTED_BY")
            return

        raise FalkorDBConnectionError(
            f"Cannot record Execution node: FalkorDB is disconnected ({self.client.last_error})."
        )

    def record_artifact(
        self,
        project_id: str,
        execution_id: str,
        artifact_id: str,
        artifact_type: str,
        name: str,
        content_preview: str,
    ) -> None:
        """Record an output artifact produced by an execution."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        preview = (content_preview[:400] + "...") if len(content_preview) > 400 else content_preview

        if self.client.is_connected:
            cypher = (
                "MATCH (e:Execution {id: $execution_id}) "
                "MERGE (a:Artifact {id: $artifact_id}) "
                "SET a.type = $artifact_type, a.name = $name, a.preview = $preview, a.created_at = timestamp() "
                "MERGE (e)-[:PRODUCED]->(a)"
            )
            self.client.query(
                graph_name,
                cypher,
                {
                    "execution_id": execution_id,
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "name": name,
                    "preview": preview,
                },
            )
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_node(
                artifact_id,
                "Artifact",
                {
                    "artifact_type": artifact_type,
                    "name": name,
                    "preview": preview,
                    "full_length": len(content_preview),
                    "created_at": time.time(),
                },
            )
            mem_graph.add_edge(execution_id, artifact_id, "PRODUCED")
            return

        raise FalkorDBConnectionError(
            f"Cannot record Artifact node: FalkorDB is disconnected ({self.client.last_error})."
        )

    def record_decision(
        self,
        project_id: str,
        execution_id: str,
        decision_id: str,
        description: str,
        rationale: str,
    ) -> None:
        """Record an architectural or routing decision made during execution."""
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        if self.client.is_connected:
            cypher = (
                "MATCH (e:Execution {id: $execution_id}) "
                "MERGE (d:Decision {id: $decision_id}) "
                "SET d.description = $description, d.rationale = $rationale, d.created_at = timestamp() "
                "MERGE (e)-[:MADE_DECISION]->(d)"
            )
            self.client.query(
                graph_name,
                cypher,
                {
                    "execution_id": execution_id,
                    "decision_id": decision_id,
                    "description": description,
                    "rationale": rationale,
                },
            )
            return

        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            mem_graph.add_node(
                decision_id,
                "Decision",
                {"description": description, "rationale": rationale, "created_at": time.time()},
            )
            mem_graph.add_edge(execution_id, decision_id, "MADE_DECISION")
            return

        raise FalkorDBConnectionError(
            f"Cannot record Decision node: FalkorDB is disconnected ({self.client.last_error})."
        )

    # ── Context Package Builder ──────────────────────────────────────────────────

    def build_context_package(
        self,
        project_id: str,
        task_id: str,
        dependency_task_ids: Optional[List[str]] = None,
        max_items: int = 5,
    ) -> Dict[str, Any]:
        """
        Builds a structured context package by inspecting FalkorDB for upstream dependencies,
        artifacts produced by prior executions, and architectural decisions.
        """
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        context_package: Dict[str, Any] = {
            "project_id": project_id,
            "task_id": task_id,
            "dependency_outputs": [],
            "relevant_decisions": [],
            "artifacts": [],
            "status": self.client.status,
            "backend": self.client.backend_mode,
        }

        # ── Branch 1: Connected to FalkorDB (Real Cypher retrieval) ───────────────
        if self.client.is_connected:
            try:
                # Query upstream dependencies, executions, artifacts, and decisions
                cypher = """
                MATCH (t:Task {id: $task_id})-[:DEPENDS_ON]->(dep:Task)
                OPTIONAL MATCH (dep)-[:EXECUTED_BY]->(ex:Execution)
                OPTIONAL MATCH (ex)-[:PRODUCED]->(art:Artifact)
                OPTIONAL MATCH (ex)-[:MADE_DECISION]->(dec:Decision)
                RETURN dep, ex, art, dec
                """
                res = self.client.query(graph_name, cypher, {"task_id": task_id})
                seen_deps: Set[str] = set()
                seen_arts: Set[str] = set()
                seen_decs: Set[str] = set()

                if res and hasattr(res, "result_set"):
                    for row in res.result_set:
                        dep_node, ex_node, art_node, dec_node = row[0], row[1], row[2], row[3]
                        if dep_node:
                            d_props = getattr(dep_node, "properties", {})
                            d_id = d_props.get("id", str(getattr(dep_node, "id", "")))
                            if d_id and d_id not in seen_deps:
                                seen_deps.add(d_id)
                                context_package["dependency_outputs"].append({
                                    "task_id": d_id,
                                    "title": d_props.get("title", d_id),
                                    "type": d_props.get("task_type", "general"),
                                })

                        if art_node:
                            a_props = getattr(art_node, "properties", {})
                            a_id = a_props.get("id", str(getattr(art_node, "id", "")))
                            if a_id and a_id not in seen_arts:
                                seen_arts.add(a_id)
                                context_package["artifacts"].append({
                                    "from_task": d_props.get("title", "Upstream"),
                                    "name": a_props.get("name", "Artifact"),
                                    "type": a_props.get("type", a_props.get("artifact_type")),
                                    "preview": a_props.get("preview", ""),
                                })

                        if dec_node:
                            dec_props = getattr(dec_node, "properties", {})
                            dec_id = dec_props.get("id", str(getattr(dec_node, "id", "")))
                            if dec_id and dec_id not in seen_decs:
                                seen_decs.add(dec_id)
                                context_package["relevant_decisions"].append({
                                    "description": dec_props.get("description", ""),
                                    "rationale": dec_props.get("rationale", ""),
                                })

                # If extra dependency IDs were provided directly
                if dependency_task_ids:
                    extra_ids = [d for d in dependency_task_ids if d not in seen_deps]
                    if extra_ids:
                        extra_cypher = """
                        MATCH (dep:Task) WHERE dep.id IN $dep_ids
                        OPTIONAL MATCH (dep)-[:EXECUTED_BY]->(ex:Execution)
                        OPTIONAL MATCH (ex)-[:PRODUCED]->(art:Artifact)
                        OPTIONAL MATCH (ex)-[:MADE_DECISION]->(dec:Decision)
                        RETURN dep, ex, art, dec
                        """
                        extra_res = self.client.query(graph_name, extra_cypher, {"dep_ids": extra_ids})
                        if extra_res and hasattr(extra_res, "result_set"):
                            for row in extra_res.result_set:
                                dep_node, ex_node, art_node, dec_node = row[0], row[1], row[2], row[3]
                                if dep_node:
                                    d_props = getattr(dep_node, "properties", {})
                                    d_id = d_props.get("id", str(getattr(dep_node, "id", "")))
                                    if d_id and d_id not in seen_deps:
                                        seen_deps.add(d_id)
                                        context_package["dependency_outputs"].append({
                                            "task_id": d_id,
                                            "title": d_props.get("title", d_id),
                                            "type": d_props.get("task_type", "general"),
                                        })
                                if art_node:
                                    a_props = getattr(art_node, "properties", {})
                                    a_id = a_props.get("id", str(getattr(art_node, "id", "")))
                                    if a_id and a_id not in seen_arts:
                                        seen_arts.add(a_id)
                                        context_package["artifacts"].append({
                                            "from_task": d_props.get("title", "Upstream"),
                                            "name": a_props.get("name", "Artifact"),
                                            "type": a_props.get("type", a_props.get("artifact_type")),
                                            "preview": a_props.get("preview", ""),
                                        })
                                if dec_node:
                                    dec_props = getattr(dec_node, "properties", {})
                                    dec_id = dec_props.get("id", str(getattr(dec_node, "id", "")))
                                    if dec_id and dec_id not in seen_decs:
                                        seen_decs.add(dec_id)
                                        context_package["relevant_decisions"].append({
                                            "description": dec_props.get("description", ""),
                                            "rationale": dec_props.get("rationale", ""),
                                        })

                context_package["artifacts"] = context_package["artifacts"][:max_items]
                context_package["relevant_decisions"] = context_package["relevant_decisions"][:max_items]
                return context_package
            except Exception as exc:
                logger.error("Failed to query FalkorDB for context package (%s): %s", graph_name, exc)
                context_package["error"] = str(exc)
                return context_package

        # ── Branch 2: In-Memory Test Mode ─────────────────────────────────────────
        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            dep_ids = set(dependency_task_ids or [])
            related_deps = mem_graph.get_related(task_id, edge_type="DEPENDS_ON", direction="out")
            for r in related_deps:
                dep_ids.add(r["node"]["id"])

            for dep_id in dep_ids:
                dep_node = mem_graph.get_node(dep_id)
                dep_title = dep_node["properties"].get("title", dep_id) if dep_node else dep_id

                exec_edges = mem_graph.get_related(dep_id, edge_type="EXECUTED_BY", direction="out")
                for ex in exec_edges:
                    ex_id = ex["node"]["id"]
                    artifact_edges = mem_graph.get_related(ex_id, edge_type="PRODUCED", direction="out")
                    for art in artifact_edges:
                        art_props = art["node"]["properties"]
                        context_package["artifacts"].append({
                            "from_task": dep_title,
                            "name": art_props.get("name"),
                            "type": art_props.get("artifact_type"),
                            "preview": art_props.get("preview"),
                        })

                    decision_edges = mem_graph.get_related(ex_id, edge_type="MADE_DECISION", direction="out")
                    for dec in decision_edges:
                        dec_props = dec["node"]["properties"]
                        context_package["relevant_decisions"].append({
                            "description": dec_props.get("description"),
                            "rationale": dec_props.get("rationale"),
                        })

                if dep_node:
                    context_package["dependency_outputs"].append({
                        "task_id": dep_id,
                        "title": dep_title,
                        "type": dep_node["properties"].get("task_type", "general"),
                    })

            context_package["artifacts"] = context_package["artifacts"][:max_items]
            context_package["relevant_decisions"] = context_package["relevant_decisions"][:max_items]
            return context_package

        # ── Branch 3: Disconnected ────────────────────────────────────────────────
        context_package["error"] = f"FalkorDB is offline ({self.client.last_error}). Graph context unavailable."
        return context_package

    # ── Graph Visualizer API ─────────────────────────────────────────────────────

    def get_project_graph(self, project_id: str) -> Dict[str, Any]:
        """
        Returns full graph snapshot with node types, labels, and links for UI visualization.
        Queries live FalkorDB via Cypher when connected.
        """
        self.ensure_connected()
        graph_name = self._get_graph_name(project_id)

        # ── Branch 1: Connected to FalkorDB ───────────────────────────────────────
        if self.client.is_connected:
            try:
                cypher = """
                MATCH (n)
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, type(r) AS rel_type, properties(r) AS rel_props, m
                """
                res = self.client.query(graph_name, cypher)
                nodes_dict: Dict[str, Dict[str, Any]] = {}
                edges_list: List[Dict[str, Any]] = []

                if res and hasattr(res, "result_set"):
                    for row in res.result_set:
                        n, rel_type, rel_props, m = row[0], row[1], row[2], row[3]
                        if n:
                            n_props = dict(getattr(n, "properties", {}))
                            n_id = n_props.get("id", str(getattr(n, "id", "")))
                            labels = getattr(n, "labels", [])
                            label = labels[0] if (labels and len(labels) > 0) else "Node"
                            if n_id not in nodes_dict:
                                nodes_dict[n_id] = {
                                    "id": n_id,
                                    "label": label,
                                    **n_props,
                                }
                        if m and rel_type:
                            m_props = dict(getattr(m, "properties", {}))
                            m_id = m_props.get("id", str(getattr(m, "id", "")))
                            labels_m = getattr(m, "labels", [])
                            label_m = labels_m[0] if (labels_m and len(labels_m) > 0) else "Node"
                            if m_id not in nodes_dict:
                                nodes_dict[m_id] = {
                                    "id": m_id,
                                    "label": label_m,
                                    **m_props,
                                }
                            edges_list.append({
                                "source": n_id,
                                "target": m_id,
                                "type": rel_type,
                                **(rel_props or {}),
                            })

                return {
                    "nodes": list(nodes_dict.values()),
                    "edges": edges_list,
                    "status": "connected",
                    "backend": "falkordb",
                    "graph_name": graph_name,
                }
            except Exception as exc:
                logger.error("Error retrieving graph from FalkorDB (%s): %s", graph_name, exc)
                return {
                    "nodes": [],
                    "edges": [],
                    "status": "error",
                    "backend": "falkordb",
                    "error": str(exc),
                }

        # ── Branch 2: In-Memory Test Mode ─────────────────────────────────────────
        if self.client.status == "in_memory_test":
            mem_graph = self.client.get_or_create_memory_graph(graph_name)
            data = mem_graph.to_graph_data()
            return {
                **data,
                "status": "in_memory_test",
                "backend": "in_memory_test",
                "graph_name": graph_name,
            }

        # ── Branch 3: Disconnected ────────────────────────────────────────────────
        return {
            "nodes": [],
            "edges": [],
            "status": "disconnected",
            "backend": "none",
            "error": f"FalkorDB is offline: {self.client.last_error or 'Connection refused'}",
            "graph_name": graph_name,
        }


# Global memory service instance
memory_service = MemoryService()
