"""
SYNQ Database Models (SQLAlchemy 2.0 style)
Operational state, task tracking, execution records, routing decisions.
FalkorDB is the source of truth for graph relationships and project memory.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Enum,
    JSON,
)
from sqlalchemy.dialects.sqlite import TEXT as SQLiteText
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProjectDomain(str, PyEnum):
    SOFTWARE = "software"
    RESEARCH = "research"
    EDUCATION = "education"
    CONTENT = "content"
    BUSINESS = "business"
    GENERAL = "general"


class ProjectStatus(str, PyEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskType(str, PyEnum):
    CODE = "code"
    RESEARCH = "research"
    WRITE = "write"
    ANALYZE = "analyze"
    PLAN = "plan"
    GENERAL = "general"


class TaskStatus(str, PyEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class ExecutionStatus(str, PyEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProviderStatus(str, PyEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNCONFIGURED = "unconfigured"


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(
        Enum(ProjectDomain, values_callable=lambda x: [e.value for e in x]),
        default=ProjectDomain.GENERAL.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(ProjectStatus, values_callable=lambda x: [e.value for e in x]),
        default=ProjectStatus.ACTIVE.value,
        nullable=False,
    )
    # Comma-separated provider IDs permitted for this project.
    # Empty string = all configured providers allowed.
    allowed_providers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Reference to the FalkorDB graph for this project.
    memory_graph_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan"
    )

    def get_allowed_provider_list(self) -> list[str]:
        if not self.allowed_providers:
            return []  # Empty = all allowed
        return [p.strip() for p in self.allowed_providers.split(",") if p.strip()]


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    parent_task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        Enum(TaskType, values_callable=lambda x: [e.value for e in x]),
        default=TaskType.GENERAL.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(TaskStatus, values_callable=lambda x: [e.value for e in x]),
        default=TaskStatus.PENDING.value,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1-10
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Comma-separated task IDs this task depends on.
    dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Position in the execution DAG (set by planner).
    execution_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Provider/model assigned by router.
    assigned_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assigned_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Human approval flag and audit trail.
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Timestamps.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    subtasks: Mapped[list["Task"]] = relationship("Task", back_populates="parent_task")
    parent_task: Mapped[Optional["Task"]] = relationship(
        "Task", back_populates="subtasks", remote_side="Task.id"
    )
    executions: Mapped[list["TaskExecution"]] = relationship(
        "TaskExecution", back_populates="task", cascade="all, delete-orphan"
    )

    def get_dependency_list(self) -> list[str]:
        if not self.dependencies:
            return []
        return [d.strip() for d in self.dependencies.split(",") if d.strip()]


class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(ExecutionStatus, values_callable=lambda x: [e.value for e in x]),
        default=ExecutionStatus.RUNNING.value,
        nullable=False,
    )
    # Context package sent to the provider (stored as JSON text).
    input_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    # Raw output from provider.
    output_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Structured output if requested.
    output_structured: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    # Validation result.
    validation_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    validation_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # Error information.
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Fallback information (if this execution was a fallback attempt).
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fallback_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Token / cost tracking.
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_estimate_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Checkpoint for recovery.
    checkpoint_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    # Timestamps.
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="executions")
    routing_decision: Mapped[Optional["RoutingDecision"]] = relationship(
        "RoutingDecision", back_populates="execution", uselist=False
    )


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False
    )
    # What the AI planner suggested (JSON).
    planner_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # What was actually selected.
    selected_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_model: Mapped[str] = mapped_column(String(200), nullable=False)
    selection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Providers considered but rejected (JSON array).
    rejected_providers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Was this overridden by the user?
    override_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    execution: Mapped["TaskExecution"] = relationship(
        "TaskExecution", back_populates="routing_decision"
    )


class ProviderCapabilityRecord(Base):
    """
    Persisted Capability Registry entries.
    Runtime health is NOT stored here — it is checked live.
    """
    __tablename__ = "provider_capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Capability flags.
    supported_task_types: Mapped[str] = mapped_column(Text, nullable=False)  # Comma-separated
    input_modalities: Mapped[str] = mapped_column(Text, nullable=False)     # Comma-separated
    output_modalities: Mapped[str] = mapped_column(Text, nullable=False)    # Comma-separated
    context_window_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_tool_calling: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=False)
    # Configuration.
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=True)
    api_key_env_var: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_source: Mapped[str] = mapped_column(
        String(50), default="official_docs", nullable=False
    )
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
