"""
Memory API Endpoints for SYNQ.
Exposes FalkorDB project memory graph, persistence status, and context packages.
"""

from fastapi import APIRouter
from memory.memory_service import memory_service

router = APIRouter(tags=["memory"])


@router.get("/projects/{project_id}/memory/status")
async def get_project_memory_status(project_id: str):
    """
    Retrieve FalkorDB connection status and persistence mode for the project.
    Indicates whether persistent FalkorDB is active or paused.
    """
    status = memory_service.get_status()
    return {
        "project_id": project_id,
        **status,
    }


@router.get("/projects/{project_id}/memory/graph")
async def get_project_memory_graph(project_id: str):
    """
    Retrieve full FalkorDB memory graph for a project.
    Returns nodes and edges formatted for visualizers (D3, React Flow).
    Includes status and backend information.
    """
    graph_data = memory_service.get_project_graph(project_id)
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    return {
        "project_id": project_id,
        "status": graph_data.get("status", "unknown"),
        "backend": graph_data.get("backend", "none"),
        "error": graph_data.get("error"),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        },
    }


@router.get("/projects/{project_id}/memory/context/{task_id}")
async def inspect_task_context(project_id: str, task_id: str):
    """
    Inspect the structured context package that would be (or was) provided to the AI agent.
    """
    context = memory_service.build_context_package(project_id, task_id)
    return context
