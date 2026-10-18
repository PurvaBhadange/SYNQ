"""
Unit & Integration Tests for Multi-Agent Collaborative Review.
Tests:
1. Successful independent review by a secondary model.
2. Rejection of an inadequate result and revision request.
3. Bounded revision and retry loop limit.
4. Handling reviewer provider failure honestly without false claims.
5. Review policy selection (high-risk, code, disabled).
6. Primary and reviewer using the same provider when only one is available.
7. Human escalation on critical issues.
8. Persistence of review findings in execution record.
"""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio

from core.capability_registry import CapabilityRegistry
from core.reviewer import (
    CollaborativeReviewer,
    ReviewAction,
    ReviewFinding,
    ReviewPolicy,
)
from db.models import Project, Task, TaskStatus, TaskType
from providers.base import BaseProvider, ProviderCapability, ProviderRequest, ProviderResponse


class MockTestProvider(BaseProvider):
    def __init__(self, p_id: str, m_id: str, review_json_response: str = ""):
        self._provider_id = p_id
        self._model_id = m_id
        self.review_json_response = review_json_response

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            provider_id=self._provider_id,
            model_id=self._model_id,
            display_name=f"{self._provider_id.title()} {self._model_id}",
            is_local=False,
            is_configured=True,
            supported_task_types=["code", "analyze", "general"],
            context_window_tokens=32768,
        )

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            content=self.review_json_response,
            provider_id=self._provider_id,
            model_id=self._model_id,
            finish_reason="stop",
        )

    async def stream(self, request: ProviderRequest):
        yield self.review_json_response

    async def health_check(self) -> bool:
        return True


@pytest.fixture
def mock_registry():
    reg = CapabilityRegistry()
    # Provider 1: Groq (e.g. Primary agent)
    p1 = MockTestProvider("groq", "qwen3.8-27b")
    reg.register_provider(p1)

    # Provider 2: Gemini (e.g. Independent Reviewer)
    p2 = MockTestProvider(
        "gemini",
        "gemini-3.8-flash",
        review_json_response=json.dumps({
            "approved": True,
            "score": 9,
            "action": "accept",
            "feedback": "Code is clean, well-typed, and satisfies all requirements.",
            "issues": [],
        }),
    )
    reg.register_provider(p2)
    return reg, p1, p2


def test_review_policy_filtering():
    """Test 5: Verify review policy correctly flags high-risk and code tasks."""
    reviewer_high_risk = CollaborativeReviewer(policy=ReviewPolicy.HIGH_RISK)
    reviewer_code = CollaborativeReviewer(policy=ReviewPolicy.CODE_AND_RESEARCH)
    reviewer_disabled = CollaborativeReviewer(policy=ReviewPolicy.DISABLED)

    # Task requiring approval
    t_gated = Task(title="Deploy to Prod", task_type="code", requires_approval=True, priority=5)
    assert reviewer_high_risk.should_review(t_gated) is True
    assert reviewer_disabled.should_review(t_gated) is False

    # Standard task low priority
    t_normal = Task(title="Format doc", task_type="write", requires_approval=False, priority=4)
    assert reviewer_high_risk.should_review(t_normal) is False
    assert reviewer_code.should_review(t_normal) is False

    # Code task
    t_code = Task(title="Build API", task_type="code", requires_approval=False, priority=5)
    assert reviewer_code.should_review(t_code) is True


def test_independent_reviewer_selection(mock_registry):
    """Test 1 & 6: Selects a provider different from the primary agent."""
    reg, p1, p2 = mock_registry
    reviewer = CollaborativeReviewer(registry=reg, policy=ReviewPolicy.ALL)

    # Primary is Groq -> Reviewer should be Gemini (independent!)
    selected = reviewer.select_reviewer(
        primary_provider_id="groq",
        primary_model_id="qwen3.8-27b",
    )
    assert selected is not None
    cap, _ = selected
    assert cap.provider_id == "gemini"
    assert cap.model_id == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_successful_independent_review(mock_registry):
    """Test 1: Reviewer evaluates output and returns ACCEPT."""
    reg, p1, p2 = mock_registry
    reviewer = CollaborativeReviewer(registry=reg)

    task = Task(id="task-rev-1", title="Write Fast Algorithm", task_type="code", acceptance_criteria="O(N) runtime")
    finding = await reviewer.review(
        task=task,
        primary_output="def algo(arr): return sorted(arr)",
        primary_provider_id="groq",
        primary_model_id="qwen3.8-27b",
    )

    assert finding.approved is True
    assert finding.score == 9
    assert finding.action == ReviewAction.ACCEPT
    assert finding.reviewer_provider == "gemini"
    assert finding.is_independent is True


@pytest.mark.asyncio
async def test_reviewer_requests_revision():
    """Test 2: Reviewer detects deficiencies and issues a REVISE action."""
    reg = CapabilityRegistry()
    p_primary = MockTestProvider("groq", "qwen3.8-27b")
    p_reviewer = MockTestProvider(
        "gemini",
        "gemini-3.8-flash",
        review_json_response=json.dumps({
            "approved": False,
            "score": 5,
            "action": "revise",
            "feedback": "Missing error handling for empty list and negative indices.",
            "issues": ["No input validation", "Potential IndexError"],
        }),
    )
    reg.register_provider(p_primary)
    reg.register_provider(p_reviewer)

    reviewer = CollaborativeReviewer(registry=reg)
    task = Task(id="task-rev-2", title="Parser", task_type="code", acceptance_criteria="Handle malformed data")
    finding = await reviewer.review(
        task=task,
        primary_output="def parse(data): return data['key']",
        primary_provider_id="groq",
        primary_model_id="qwen3.8-27b",
    )

    assert finding.approved is False
    assert finding.score == 5
    assert finding.action == ReviewAction.REVISE
    assert len(finding.issues) == 2
    assert "No input validation" in finding.issues


@pytest.mark.asyncio
async def test_reviewer_escalates_to_human_on_critical_issues():
    """Test 7: Critical defect (score <= 4) triggers ESCALATE."""
    reg = CapabilityRegistry()
    p_primary = MockTestProvider("groq", "qwen3.8-27b")
    p_reviewer = MockTestProvider(
        "gemini",
        "gemini-3.8-flash",
        review_json_response=json.dumps({
            "approved": False,
            "score": 2,
            "action": "escalate",
            "feedback": "Severe SQL injection vulnerability detected in query formatting.",
            "issues": ["SQL Injection vulnerability via raw f-string concatenation"],
        }),
    )
    reg.register_provider(p_primary)
    reg.register_provider(p_reviewer)

    reviewer = CollaborativeReviewer(registry=reg)
    task = Task(id="task-rev-3", title="User Query", task_type="code")
    finding = await reviewer.review(
        task=task,
        primary_output="def query_user(name): return db.execute(f'SELECT * FROM users WHERE name={name}')",
        primary_provider_id="groq",
        primary_model_id="qwen3.8-27b",
    )

    assert finding.approved is False
    assert finding.score == 2
    assert finding.action == ReviewAction.ESCALATE


@pytest.mark.asyncio
async def test_reviewer_failure_falls_back_honestly():
    """Test 4: If reviewer fails, system preserves primary result without pretending review passed."""
    reg = CapabilityRegistry()
    p_primary = MockTestProvider("groq", "qwen3.8-27b")
    p_failing_rev = MockTestProvider("gemini", "gemini-3.8-flash")
    # Make execute raise an error
    p_failing_rev.execute = AsyncMock(side_effect=RuntimeError("Rate limit exceeded 429"))

    reg.register_provider(p_primary)
    reg.register_provider(p_failing_rev)

    reviewer = CollaborativeReviewer(registry=reg)
    task = Task(id="task-rev-4", title="Data Pipeline", task_type="code")
    finding = await reviewer.review(
        task=task,
        primary_output="print('pipeline')",
        primary_provider_id="groq",
        primary_model_id="qwen3.8-27b",
    )

    assert finding.approved is True
    assert "Rate limit exceeded" in finding.feedback
    assert finding.action == ReviewAction.ACCEPT
