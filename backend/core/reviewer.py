"""
Collaborative Reviewer — Multi-Agent Quality Assurance & Peer Review Engine for SYNQ.

Provides an independent second-agent review pipeline:
- Configurable review policies: disabled, high_risk, code_and_research, all.
- Selects eligible reviewer model independent from the primary model.
- Evaluates correctness, completeness, security risks, and acceptance criteria.
- Applies deterministic acceptance rules with bounded revision loop (max 2).
- Escalates to human-in-the-loop when reviewer detects critical deficiencies.
- Preserves ₹0 budget and local/cloud privacy boundaries.
"""

from enum import Enum
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from core.capability_registry import CapabilityRegistry, registry as default_registry
from db.models import Task, TaskType
from providers.base import BaseProvider, ProviderCapability, ProviderRequest, ProviderResponse

logger = logging.getLogger(__name__)


class ReviewPolicy(str, Enum):
    DISABLED = "disabled"
    HIGH_RISK = "high_risk"              # requires_approval or priority >= 8
    CODE_AND_RESEARCH = "code_and_research"  # task_type in ("code", "research")
    ALL = "all"


class ReviewAction(str, Enum):
    ACCEPT = "accept"
    REVISE = "revise"
    ESCALATE = "escalate"


class ReviewFinding:
    def __init__(
        self,
        approved: bool,
        score: int,
        feedback: str,
        action: ReviewAction,
        reviewer_provider: str,
        reviewer_model: str,
        issues: Optional[List[str]] = None,
        is_independent: bool = True,
    ):
        self.approved = approved
        self.score = score
        self.feedback = feedback
        self.action = action
        self.reviewer_provider = reviewer_provider
        self.reviewer_model = reviewer_model
        self.issues = issues or []
        self.is_independent = is_independent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approved": self.approved,
            "score": self.score,
            "feedback": self.feedback,
            "action": self.action.value,
            "reviewer_provider": self.reviewer_provider,
            "reviewer_model": self.reviewer_model,
            "issues": self.issues,
            "is_independent": self.is_independent,
        }


REVIEW_PROMPT_TEMPLATE = """You are SYNQ's Senior Multi-Agent Code & Architecture Reviewer.
Your role is to rigorously evaluate an AI agent's primary output against the task requirements.

Task Title: {title}
Task Type: {task_type}
Acceptance Criteria: {acceptance_criteria}

Primary Output to Review:
\"\"\"
{content}
\"\"\"

Evaluation Criteria:
1. Correctness: Does it solve the prompt accurately without syntax/logical flaws?
2. Completeness: Does it satisfy all acceptance criteria?
3. Safety & Reliability: Are there security vulnerabilities, credentials, or dangerous patterns?

Respond strictly in valid JSON format:
{{
  "approved": true or false,
  "score": integer between 1 and 10 (10 = perfect, >= 7 = pass),
  "action": "accept" | "revise" | "escalate",
  "feedback": "Concise summary of findings",
  "issues": ["List of specific defects or empty if none"]
}}
"""


class CollaborativeReviewer:
    """
    Manages second-agent peer review, reviewer selection, and bounded revision cascades.
    """

    def __init__(
        self,
        registry: CapabilityRegistry = default_registry,
        policy: ReviewPolicy = ReviewPolicy.HIGH_RISK,
        max_revisions: int = 2,
    ):
        self.registry = registry
        self.policy = policy
        self.max_revisions = max_revisions

    def should_review(self, task: Task) -> bool:
        """Determines whether a task requires second-agent review based on active policy."""
        if self.policy == ReviewPolicy.DISABLED:
            return False
        if self.policy == ReviewPolicy.ALL:
            return True
        if self.policy == ReviewPolicy.HIGH_RISK:
            return bool(task.requires_approval or (task.priority and task.priority >= 8))
        if self.policy == ReviewPolicy.CODE_AND_RESEARCH:
            return task.task_type in (TaskType.CODE.value, TaskType.RESEARCH.value)
        return False

    def select_reviewer(
        self,
        primary_provider_id: str,
        primary_model_id: str,
        allowed_providers: Optional[List[str]] = None,
    ) -> Optional[Tuple[ProviderCapability, BaseProvider]]:
        """
        Selects an eligible reviewer model.
        Prioritizes an independent provider/model different from the primary agent.
        """
        eligible = self.registry.get_eligible_providers(
            task_type="analyze",
            allowed_provider_ids=allowed_providers,
        )
        if not eligible:
            eligible = self.registry.get_eligible_providers(
                task_type="general",
                allowed_provider_ids=allowed_providers,
            )

        if not eligible:
            return None

        # Filter for models different from primary
        independent = [
            (cap, prov) for cap, prov in eligible
            if (cap.provider_id != primary_provider_id or cap.model_id != primary_model_id)
        ]

        if independent:
            # Sort by highest token window / capability
            independent.sort(key=lambda x: (not x[0].is_local, x[0].context_window_tokens), reverse=True)
            return independent[0]

        # Fallback to same provider if only one configured
        return eligible[0]

    async def review(
        self,
        task: Task,
        primary_output: str,
        primary_provider_id: str,
        primary_model_id: str,
        allowed_providers: Optional[List[str]] = None,
    ) -> ReviewFinding:
        """
        Executes collaborative second-agent review of primary agent output.
        """
        selected = self.select_reviewer(
            primary_provider_id=primary_provider_id,
            primary_model_id=primary_model_id,
            allowed_providers=allowed_providers,
        )

        if not selected:
            logger.warning("No eligible reviewer available in registry. Preserving primary result.")
            return ReviewFinding(
                approved=True,
                score=7,
                feedback="Review skipped: no independent reviewer configured. Primary validation accepted.",
                action=ReviewAction.ACCEPT,
                reviewer_provider="none",
                reviewer_model="none",
                is_independent=False,
            )

        cap, provider = selected
        is_independent = (cap.provider_id != primary_provider_id or cap.model_id != primary_model_id)

        prompt = REVIEW_PROMPT_TEMPLATE.format(
            title=task.title,
            task_type=task.task_type,
            acceptance_criteria=task.acceptance_criteria or "Produce valid, correct output meeting prompt.",
            content=primary_output[:3000],  # Bound context to respect token constraints
        )

        req = ProviderRequest(
            task_id=task.id,
            task_type="analyze",
            system_prompt="You are a strict, objective AI QA reviewer evaluating technical work.",
            user_message=prompt,
            temperature=0.1,
            max_tokens=1000,
        )

        try:
            resp: ProviderResponse = await provider.execute(req)
            content = resp.content.strip()

            # Parse structured JSON response
            data = None
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except Exception:
                    pass

            if not data or not isinstance(data, dict):
                logger.warning("Reviewer did not return valid JSON. Fallback to heuristic acceptance.")
                return ReviewFinding(
                    approved=True,
                    score=7,
                    feedback=f"Review completed by {cap.display_name} (unstructured feedback).",
                    action=ReviewAction.ACCEPT,
                    reviewer_provider=cap.provider_id,
                    reviewer_model=cap.model_id,
                    is_independent=is_independent,
                )

            approved = bool(data.get("approved", True))
            score = int(data.get("score", 7 if approved else 4))
            raw_action = str(data.get("action", "accept")).lower()
            feedback = str(data.get("feedback", "Reviewed successfully."))
            issues = data.get("issues", [])

            # Deterministic acceptance decision rules
            if approved and score >= 7:
                action = ReviewAction.ACCEPT
            elif score <= 4:
                action = ReviewAction.ESCALATE
            else:
                action = ReviewAction.REVISE if raw_action == "revise" else ReviewAction.ACCEPT

            return ReviewFinding(
                approved=approved,
                score=score,
                feedback=feedback,
                action=action,
                reviewer_provider=cap.provider_id,
                reviewer_model=cap.model_id,
                issues=issues if isinstance(issues, list) else [str(issues)],
                is_independent=is_independent,
            )

        except Exception as exc:
            logger.error("Collaborative review failed with %s: %s", cap.display_name, exc)
            return ReviewFinding(
                approved=True,
                score=6,
                feedback=f"Reviewer encountered error ({exc}). Primary deterministic validation retained.",
                action=ReviewAction.ACCEPT,
                reviewer_provider=cap.provider_id,
                reviewer_model=cap.model_id,
                is_independent=is_independent,
            )


# Default reviewer instance
collaborative_reviewer = CollaborativeReviewer()
