"""
Planner — Hybrid AI and Deterministic Task Decomposition Engine for SYNQ.

Decomposes complex user requests into directed acyclic graph (DAG) of subtasks:
- Tries available AI provider with structured JSON prompt.
- Validates DAG topology (detects cycles, verifies dependency integrity).
- Provides deterministic fallback if AI providers are unreachable or unconfigured.
- Computes topological execution order.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.capability_registry import CapabilityRegistry, registry as default_registry
from providers.base import BaseProvider, ProviderRequest

logger = logging.getLogger(__name__)


@dataclass
class TaskProposal:
    index: int
    title: str
    description: str
    task_type: str  # "code", "research", "write", "analyze", "plan", "general"
    priority: int  # 1-10
    dependencies: List[int] = field(default_factory=list)  # indices of tasks it depends on
    acceptance_criteria: str = ""
    suggested_provider: Optional[str] = None
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "description": self.description,
            "task_type": self.task_type,
            "priority": self.priority,
            "dependencies": self.dependencies,
            "acceptance_criteria": self.acceptance_criteria,
            "suggested_provider": self.suggested_provider,
            "requires_approval": self.requires_approval,
        }


@dataclass
class PlanResult:
    goal: str
    tasks: List[TaskProposal]
    execution_order: List[int]
    is_dag_valid: bool
    planner_type: str  # "ai" or "deterministic_fallback"
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "execution_order": self.execution_order,
            "is_dag_valid": self.is_dag_valid,
            "planner_type": self.planner_type,
            "reasoning": self.reasoning,
        }


PLANNER_SYSTEM_PROMPT = """You are SYNQ's Senior AI Project Architect and Planner.
Given a user's project goal or request, decompose it into a clear, logical DAG (Directed Acyclic Graph) of distinct subtasks.
Each task must be specialized and assignable to a domain agent.

You MUST reply with a pure JSON object adhering to this schema:
{
  "reasoning": "Brief explanation of the decomposition strategy",
  "tasks": [
    {
      "index": 0,
      "title": "Short title",
      "description": "Clear instructions for what to produce",
      "task_type": "code | research | write | analyze | general",
      "priority": 1-10,
      "dependencies": [indices of tasks that must complete before this one],
      "acceptance_criteria": "Measurable criteria for completion",
      "suggested_provider": "gemini | ollama | any",
      "requires_approval": false
    }
  ]
}
Ensure there are NO circular dependencies. Task index 0 should usually have no dependencies.
Do not include any markdown outside of the JSON block.
"""


class Planner:
    """
    Decomposes goals into structured subtasks with DAG dependency verification.
    """

    def __init__(self, registry: CapabilityRegistry = default_registry):
        self.registry = registry

    async def plan(self, goal: str, domain: str = "general") -> PlanResult:
        """
        Decompose a goal into tasks using available AI provider, with deterministic fallback.
        """
        # Try AI planning first (prioritizing high-speed frontier cloud models like Groq LPU / Gemini)
        eligible = self.registry.get_eligible_providers(task_type="plan")
        if not eligible:
            eligible = self.registry.get_eligible_providers(task_type="general")

        eligible.sort(key=lambda item: (item[0].provider_id == "groq", not item[0].is_local), reverse=True)

        for cap, provider in eligible:
            try:
                plan_result = await self._plan_with_provider(provider, goal, domain)
                if plan_result and plan_result.is_dag_valid:
                    return plan_result
            except Exception as exc:
                logger.warning("AI planner failed with provider %s: %s", cap.display_name, exc)

        # Fallback to deterministic planning
        logger.info("Using deterministic planner fallback for goal: %s", goal[:50])
        return self._deterministic_plan(goal, domain)

    async def _plan_with_provider(
        self, provider: BaseProvider, goal: str, domain: str
    ) -> Optional[PlanResult]:
        req = ProviderRequest(
            task_id="plan-decomp",
            task_type="plan",
            system_prompt=PLANNER_SYSTEM_PROMPT,
            user_message=f"Project domain: {domain}\nProject goal: {goal}",
            temperature=0.2,
            max_tokens=2048,
        )
        resp = await provider.execute(req)
        content = resp.content.strip()

        # Extract JSON from potential code block
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return None

        parsed = json.loads(json_match.group(0))
        tasks_data = parsed.get("tasks", [])
        if not tasks_data:
            return None

        VALID_TASK_TYPES = {"code", "research", "write", "analyze", "plan", "general"}

        def _clean_type(raw: Any) -> str:
            if not raw or not isinstance(raw, str):
                return "general"
            cleaned = raw.lower().strip()
            if cleaned in VALID_TASK_TYPES:
                return cleaned
            for token in re.split(r"[\s,|/]+", cleaned):
                if token in VALID_TASK_TYPES:
                    return token
            return "general"

        task_proposals: List[TaskProposal] = []
        for idx, t in enumerate(tasks_data):
            task_proposals.append(
                TaskProposal(
                    index=idx,
                    title=t.get("title", f"Subtask {idx + 1}"),
                    description=t.get("description", ""),
                    task_type=_clean_type(t.get("task_type")),
                    priority=int(t.get("priority", 5)),
                    dependencies=[int(d) for d in t.get("dependencies", []) if int(d) < idx],
                    acceptance_criteria=t.get("acceptance_criteria", ""),
                    suggested_provider=t.get("suggested_provider"),
                    requires_approval=bool(t.get("requires_approval", False)),
                )
            )

        order, is_valid = self._topological_sort(task_proposals)
        return PlanResult(
            goal=goal,
            tasks=task_proposals,
            execution_order=order,
            is_dag_valid=is_valid,
            planner_type="ai",
            reasoning=parsed.get("reasoning", "AI task decomposition completed."),
        )

    def _deterministic_plan(self, goal: str, domain: str) -> PlanResult:
        """
        Deterministic decomposition based on domain and common software/research lifecycle.
        """
        tasks: List[TaskProposal] = []

        if domain == "software" or any(kw in goal.lower() for kw in ["app", "code", "api", "build", "develop"]):
            tasks = [
                TaskProposal(
                    index=0,
                    title=f"Architecture & Specification for: {goal[:40]}",
                    description=f"Analyze requirements and design technical architecture for: {goal}",
                    task_type="analyze",
                    priority=8,
                    dependencies=[],
                    acceptance_criteria="System architecture, data structures, and component boundaries documented.",
                ),
                TaskProposal(
                    index=1,
                    title=f"Core Implementation for: {goal[:40]}",
                    description=f"Implement primary modules and business logic based on specification.",
                    task_type="code",
                    priority=9,
                    dependencies=[0],
                    acceptance_criteria="Functional code matching architecture specification.",
                ),
                TaskProposal(
                    index=2,
                    title=f"Verification & Test Suite",
                    description=f"Write test cases and verify implementation against edge cases.",
                    task_type="code",
                    priority=7,
                    dependencies=[1],
                    acceptance_criteria="Unit and integration tests pass cleanly.",
                ),
                TaskProposal(
                    index=3,
                    title=f"Documentation & Usage Guide",
                    description=f"Write comprehensive documentation, API contracts, and usage instructions.",
                    task_type="write",
                    priority=5,
                    dependencies=[1, 2],
                    acceptance_criteria="README and usage instructions clearly documented.",
                ),
            ]
        elif domain == "research" or any(kw in goal.lower() for kw in ["research", "investigate", "study", "compare"]):
            tasks = [
                TaskProposal(
                    index=0,
                    title=f"Literature & Evidence Gathering: {goal[:40]}",
                    description=f"Identify key primary sources, prior work, and benchmark datasets for {goal}",
                    task_type="research",
                    priority=8,
                    dependencies=[],
                    acceptance_criteria="Identified sources, verified citations, and background summaries.",
                ),
                TaskProposal(
                    index=1,
                    title=f"Comparative Synthesis & Findings",
                    description=f"Synthesize evidence, evaluate trade-offs, and outline core findings.",
                    task_type="analyze",
                    priority=7,
                    dependencies=[0],
                    acceptance_criteria="Structured analysis comparing findings with evidence.",
                ),
                TaskProposal(
                    index=2,
                    title=f"Final Research Report",
                    description=f"Draft comprehensive research paper with citations, takeaways, and next steps.",
                    task_type="write",
                    priority=6,
                    dependencies=[1],
                    acceptance_criteria="Formatted report with abstract, key findings, and references.",
                ),
            ]
        else:
            tasks = [
                TaskProposal(
                    index=0,
                    title=f"Analysis: {goal[:40]}",
                    description=f"Analyze goals, constraints, and prerequisites for: {goal}",
                    task_type="analyze",
                    priority=7,
                    dependencies=[],
                    acceptance_criteria="Clear breakdown of problem scope and objectives.",
                ),
                TaskProposal(
                    index=1,
                    title=f"Execution: {goal[:40]}",
                    description=f"Execute core deliverables for: {goal}",
                    task_type="general",
                    priority=8,
                    dependencies=[0],
                    acceptance_criteria="Deliverable meets user goal specifications.",
                ),
                TaskProposal(
                    index=2,
                    title=f"Review & Summary",
                    description=f"Review outputs, summarize results, and suggest follow-up items.",
                    task_type="write",
                    priority=5,
                    dependencies=[1],
                    acceptance_criteria="Summary of completed tasks and verification.",
                ),
            ]

        order, is_valid = self._topological_sort(tasks)
        return PlanResult(
            goal=goal,
            tasks=tasks,
            execution_order=order,
            is_dag_valid=is_valid,
            planner_type="deterministic_fallback",
            reasoning="Deterministic decomposition applied based on project domain.",
        )

    def _topological_sort(self, tasks: List[TaskProposal]) -> tuple[List[int], bool]:
        """
        Kahn's algorithm for topological sorting of tasks.
        Returns (ordered_indices, is_acyclic).
        """
        in_degree = {t.index: 0 for t in tasks}
        adj = {t.index: [] for t in tasks}

        for t in tasks:
            for dep in t.dependencies:
                if dep in adj:
                    adj[dep].append(t.index)
                    in_degree[t.index] += 1

        queue = [idx for idx, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        is_valid = len(order) == len(tasks)
        if not is_valid:
            # Fallback to sequential order if cycle detected
            order = [t.index for t in tasks]

        return order, is_valid


planner = Planner()
