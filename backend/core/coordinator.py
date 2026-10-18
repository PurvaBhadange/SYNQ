"""
Task Coordinator — Central DAG Execution and Agent Orchestration Engine for SYNQ.

Coordinates multi-agent task execution:
- Respects topological dependency order.
- Fetches upstream context from memory service (FalkorDB).
- Invokes deterministic router for optimal provider selection.
- Executes tasks with real-time streaming event dispatch (WebSocket/SSE).
- Validates outputs via OutputValidator.
- Manages automatic retry and fallback cascades on provider failure.
- Commits results to SQLite operational DB and FalkorDB knowledge graph.
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from core.capability_registry import CapabilityRegistry, registry as default_registry
from core.reviewer import CollaborativeReviewer, collaborative_reviewer as default_reviewer, ReviewAction, ReviewPolicy
from core.router import Router, router as default_router, health_tracker
from core.validator import OutputValidator, validator as default_validator
from db.models import ExecutionStatus, Project, RoutingDecision, Task, TaskExecution, TaskStatus
from db.session import get_session_context
from memory.falkordb_client import FalkorDBConnectionError
from memory.memory_service import MemoryService, memory_service as default_memory_service
from providers.base import BaseProvider, ProviderError, ProviderRequest, ProviderResponse
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Event listener type for WebSockets / SSE
EventListener = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class TaskCoordinator:
    """
    Coordinates task execution, fallback recovery, validation, and real-time streaming.
    """

    def __init__(
        self,
        router: Router = default_router,
        validator: OutputValidator = default_validator,
        memory: MemoryService = default_memory_service,
        registry: CapabilityRegistry = default_registry,
        reviewer: CollaborativeReviewer = default_reviewer,
    ):
        self.router = router
        self.validator = validator
        self.memory = memory
        self.registry = registry
        self.reviewer = reviewer
        self._listeners: List[EventListener] = []

    def add_event_listener(self, listener: EventListener) -> None:
        self._listeners.append(listener)

    def remove_event_listener(self, listener: EventListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit_event(self, project_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """Dispatch real-time events to all active listeners."""
        payload = {
            "project_id": project_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        for listener in self._listeners:
            try:
                await listener(project_id, payload)
            except Exception as exc:
                logger.debug("Error delivering event to listener: %s", exc)

    async def execute_task(
        self,
        task_id: str,
        user_override_provider: Optional[str] = None,
        user_override_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a single task with routing, fallback, and validation.
        """
        async with get_session_context() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found")

            project_id = task.project_id

            # Check if approval required and not granted
            if task.requires_approval and task.status != TaskStatus.ASSIGNED.value:
                task.status = TaskStatus.AWAITING_APPROVAL.value
                await session.commit()
                await self.emit_event(
                    project_id,
                    "task_awaiting_approval",
                    {"task_id": task_id, "title": task.title},
                )
                return {"status": "awaiting_approval", "task_id": task_id}

            # Check upstream dependencies
            dep_ids = task.get_dependency_list()
            if dep_ids:
                dep_result = await session.execute(select(Task).where(Task.id.in_(dep_ids)))
                dep_tasks = dep_result.scalars().all()
                incomplete = [d for d in dep_tasks if d.status != TaskStatus.COMPLETED.value]
                if incomplete:
                    names = [d.title for d in incomplete]
                    raise RuntimeError(f"Cannot execute task: dependencies not yet completed: {names}")

            # Mark task running
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.now(timezone.utc)
            await session.commit()

        await self.emit_event(
            project_id,
            "task_started",
            {"task_id": task_id, "title": task.title, "task_type": task.task_type},
        )

        # 1. Build context package from FalkorDB
        context_package = self.memory.build_context_package(
            project_id=project_id,
            task_id=task_id,
            dependency_task_ids=dep_ids,
        )

        # 2. Route task to provider
        async with get_session_context() as session:
            proj_res = await session.execute(select(Project).where(Project.id == project_id))
            proj = proj_res.scalar_one_or_none()
            allowed = proj.get_allowed_provider_list() if proj else []

        norm_task_type = task.task_type.value if hasattr(task.task_type, "value") else str(task.task_type)
        route_res = await self.router.route(
            task_type=norm_task_type,
            task_priority=task.priority,
            allowed_providers=allowed or None,
            user_override_provider=user_override_provider,
            user_override_model=user_override_model,
        )

        # List of candidate attempts: primary winner, followed by fallbacks
        candidates = [
            (
                route_res.selected_provider_id,
                route_res.selected_model_id,
                route_res.selected_provider,
                route_res.selection_reason,
                False,
            )
        ]
        for fb in route_res.fallback_candidates:
            candidates.append((fb.provider_id, fb.model_id, fb.provider, fb.reason, True))

        last_error = None

        for attempt_idx, (p_id, m_id, provider_instance, reason, is_fallback) in enumerate(candidates, start=1):
            execution_id = str(uuid.uuid4())
            await self.emit_event(
                project_id,
                "agent_assigned",
                {
                    "task_id": task_id,
                    "attempt": attempt_idx,
                    "provider_id": p_id,
                    "model_id": m_id,
                    "is_fallback": is_fallback,
                    "reason": reason,
                },
            )

            # Record routing decision in DB
            async with get_session_context() as session:
                t_res = await session.execute(select(Task).where(Task.id == task_id))
                t_current = t_res.scalar_one()
                t_current.assigned_provider = p_id
                t_current.assigned_model = m_id
                # Record execution row
                exec_record = TaskExecution(
                    id=execution_id,
                    task_id=task_id,
                    attempt_number=attempt_idx,
                    provider_id=p_id,
                    model_id=m_id,
                    status=ExecutionStatus.RUNNING.value,
                    input_context=json.dumps(context_package),
                    is_fallback=is_fallback,
                    fallback_reason=f"Previous attempt failed: {last_error}" if is_fallback else None,
                )
                session.add(exec_record)

                r_decision = RoutingDecision(
                    task_id=task_id,
                    execution_id=execution_id,
                    selected_provider=p_id,
                    selected_model=m_id,
                    selection_reason=reason,
                    rejected_providers=json.dumps([r.__dict__ for r in route_res.rejected_candidates]),
                    override_by_user=bool(user_override_provider),
                )
                session.add(r_decision)
                await session.commit()

            # Record execution node in FalkorDB (safely)
            try:
                self.memory.record_execution_node(
                    project_id=project_id,
                    task_id=task_id,
                    execution_id=execution_id,
                    provider_id=p_id,
                    model_id=m_id,
                    status="running",
                )
            except FalkorDBConnectionError as falkor_exc:
                logger.warning("FalkorDB offline during execution node recording: %s. Operational record safe in SQLite.", falkor_exc)

            # Execute via provider with streaming tokens
            try:
                system_prompt = (
                    f"You are SYNQ's specialized AI Agent for task type: '{task.task_type}'.\n"
                    f"Deliver high quality, precise, and verified results.\n"
                    f"Task Acceptance Criteria: {task.acceptance_criteria or 'Not specified'}"
                )

                # Format user prompt with context package
                user_msg_parts = [
                    f"Task Title: {task.title}",
                    f"Task Description:\n{task.description or 'No additional details.'}",
                ]
                if context_package.get("artifacts"):
                    user_msg_parts.append("\nPrevious Shared Project Artifacts:")
                    for art in context_package["artifacts"]:
                        user_msg_parts.append(f"- [{art['type']}] {art['name']}: {art['preview']}")

                if context_package.get("relevant_decisions"):
                    user_msg_parts.append("\nPrevious Architectural Decisions:")
                    for dec in context_package["relevant_decisions"]:
                        user_msg_parts.append(f"- {dec['description']} (Rationale: {dec['rationale']})")

                # Web search enrichment via Tavily for research and analysis tasks
                if task.task_type in ("research", "analyze") or "search" in (task.description or "").lower():
                    try:
                        from tools.tavily import tavily_client
                        if tavily_client.is_configured:
                            search_query = f"{task.title} {task.description or ''}".strip()[:200]
                            search_res = await tavily_client.search(search_query)
                            if search_res.get("answer") or search_res.get("results"):
                                user_msg_parts.append("\n--- Real-Time Web Intelligence (Tavily Search) ---")
                                if search_res.get("answer"):
                                    user_msg_parts.append(f"Direct Fact Synthesis: {search_res['answer']}\n")
                                for r in search_res.get("results", [])[:3]:
                                    user_msg_parts.append(f"- [{r['title']}] ({r['url']}): {r['content'][:300]}")
                                user_msg_parts.append("--------------------------------------------------\n")
                    except Exception as tavily_exc:
                        logger.debug("Tavily search enrichment skipped: %s", tavily_exc)

                req = ProviderRequest(
                    task_id=task_id,
                    task_type=task.task_type,
                    system_prompt=system_prompt,
                    user_message="\n".join(user_msg_parts),
                    context=context_package,
                    temperature=0.3,
                    max_tokens=4096,
                )

                accumulated_tokens: List[str] = []

                # Stream response tokens to WebSocket
                async for chunk in provider_instance.stream(req):
                    accumulated_tokens.append(chunk)
                    await self.emit_event(
                        project_id,
                        "task_token",
                        {"task_id": task_id, "token": chunk},
                    )

                full_content = "".join(accumulated_tokens)

                # Validate output
                val_result = self.validator.validate(
                    task_type=task.task_type,
                    content=full_content,
                    acceptance_criteria=task.acceptance_criteria,
                )

                # If validation failed, mark degraded and continue fallback loop
                if not val_result.passed:
                    last_error = f"Validation failed: {val_result.summary}"
                    self.router.health.mark_degraded(p_id, m_id, duration=60)
                    async with get_session_context() as session:
                        ex_res = await session.execute(
                            select(TaskExecution).where(TaskExecution.id == execution_id)
                        )
                        ex = ex_res.scalar_one()
                        ex.status = ExecutionStatus.FAILED.value
                        ex.output_raw = full_content
                        ex.validation_passed = False
                        ex.validation_result = json.dumps(val_result.to_dict())
                        ex.error_message = last_error
                        await session.commit()
                    continue

                # Collaborative Review Stage (Improvement 4)
                review_dict = None
                if self.reviewer.should_review(task):
                    await self.emit_event(
                        project_id,
                        "task_review_started",
                        {"task_id": task_id, "primary_provider": p_id, "primary_model": m_id},
                    )

                    review_finding = await self.reviewer.review(
                        task=task,
                        primary_output=full_content,
                        primary_provider_id=p_id,
                        primary_model_id=m_id,
                        allowed_providers=allowed,
                    )
                    review_dict = review_finding.to_dict()

                    await self.emit_event(
                        project_id,
                        "task_review_completed",
                        {
                            "task_id": task_id,
                            "finding": review_dict,
                        },
                    )

                    # Bounded revision request
                    if review_finding.action == ReviewAction.REVISE and attempt <= self.reviewer.max_revisions:
                        last_error = f"Revision requested by {review_finding.reviewer_provider}: {review_finding.feedback}"
                        user_msg_parts.append(
                            f"\n[PEER REVIEW FEEDBACK from {review_finding.reviewer_provider}]:\n"
                            f"Issues: {', '.join(review_finding.issues)}\n"
                            f"Recommendation: {review_finding.feedback}\n"
                            f"Please provide an updated, revised deliverable resolving these issues."
                        )
                        async with get_session_context() as session:
                            ex_res = await session.execute(
                                select(TaskExecution).where(TaskExecution.id == execution_id)
                            )
                            ex = ex_res.scalar_one()
                            ex.status = ExecutionStatus.FAILED.value
                            ex.output_raw = full_content
                            ex.validation_passed = False
                            val_data = val_result.to_dict()
                            val_data["collaborative_review"] = review_dict
                            ex.validation_result = json.dumps(val_data)
                            ex.error_message = last_error
                            await session.commit()
                        continue

                    # Human escalation on critical issues or max revisions exceeded
                    if review_finding.action == ReviewAction.ESCALATE or (
                        review_finding.action == ReviewAction.REVISE and attempt > self.reviewer.max_revisions
                    ):
                        escalate_reason = f"Collaborative review escalated ({review_finding.reviewer_provider}): {review_finding.feedback}"
                        async with get_session_context() as session:
                            t_res = await session.execute(select(Task).where(Task.id == task_id))
                            t = t_res.scalar_one()
                            t.status = TaskStatus.AWAITING_APPROVAL.value
                            t.approval_reason = escalate_reason
                            await session.commit()

                        await self.emit_event(
                            project_id,
                            "task_awaiting_approval",
                            {
                                "task_id": task_id,
                                "title": task.title,
                                "reason": escalate_reason,
                                "review_finding": review_dict,
                            },
                        )
                        return {
                            "status": "awaiting_approval",
                            "task_id": task_id,
                            "review_escalation": review_dict,
                        }

                # Execution succeeded!
                artifact_id = str(uuid.uuid4())
                decision_id = str(uuid.uuid4())

                # Persist to database
                val_payload = val_result.to_dict()
                if review_dict:
                    val_payload["collaborative_review"] = review_dict

                async with get_session_context() as session:
                    t_res = await session.execute(select(Task).where(Task.id == task_id))
                    t = t_res.scalar_one()
                    t.status = TaskStatus.COMPLETED.value
                    t.completed_at = datetime.now(timezone.utc)

                    ex_res = await session.execute(
                        select(TaskExecution).where(TaskExecution.id == execution_id)
                    )
                    ex = ex_res.scalar_one()
                    ex.status = ExecutionStatus.SUCCEEDED.value
                    ex.completed_at = datetime.now(timezone.utc)
                    ex.output_raw = full_content
                    ex.validation_passed = True
                    ex.validation_result = json.dumps(val_payload)
                    await session.commit()

                # Record Artifact and Decision in FalkorDB (safely)
                try:
                    self.memory.record_artifact(
                        project_id=project_id,
                        execution_id=execution_id,
                        artifact_id=artifact_id,
                        artifact_type=task.task_type,
                        name=f"Output for: {task.title[:30]}",
                        content_preview=full_content,
                    )
                    self.memory.record_decision(
                        project_id=project_id,
                        execution_id=execution_id,
                        decision_id=decision_id,
                        description=f"Routed {task.title} to {p_id}:{m_id}",
                        rationale=reason,
                    )
                except FalkorDBConnectionError as falkor_exc:
                    logger.warning("FalkorDB offline during task artifact persistence: %s. Operational record safe in SQLite.", falkor_exc)

                await self.emit_event(
                    project_id,
                    "task_completed",
                    {
                        "task_id": task_id,
                        "title": task.title,
                        "provider_id": p_id,
                        "model_id": m_id,
                        "validation": val_result.to_dict(),
                        "output": full_content,
                    },
                )

                return {
                    "status": "succeeded",
                    "task_id": task_id,
                    "provider_id": p_id,
                    "model_id": m_id,
                    "output": full_content,
                    "validation": val_result.to_dict(),
                }

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Execution attempt %s on %s:%s failed: %s", attempt_idx, p_id, m_id, exc
                )
                self.router.health.mark_degraded(p_id, m_id, duration=120)

                async with get_session_context() as session:
                    ex_res = await session.execute(
                        select(TaskExecution).where(TaskExecution.id == execution_id)
                    )
                    ex = ex_res.scalar_one_or_none()
                    if ex:
                        ex.status = ExecutionStatus.FAILED.value
                        ex.error_message = str(exc)
                        await session.commit()

        # If all candidates exhausted, mark task FAILED
        async with get_session_context() as session:
            t_res = await session.execute(select(Task).where(Task.id == task_id))
            t = t_res.scalar_one()
            t.status = TaskStatus.FAILED.value
            await session.commit()

        await self.emit_event(
            project_id,
            "task_failed",
            {"task_id": task_id, "title": task.title, "error": last_error},
        )

        return {
            "status": "failed",
            "task_id": task_id,
            "error": f"All eligible providers failed. Last error: {last_error}",
        }


coordinator = TaskCoordinator()
