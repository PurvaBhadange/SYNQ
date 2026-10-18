"""
Router — Deterministic AI Provider Routing Engine for SYNQ.

Principles:
- Purely deterministic: No LLM decides routing; algorithmic scoring guarantees
  reproducibility, auditability, and safety.
- Multi-stage filtering:
    1. Task type compatibility
    2. Configuration status (API keys / endpoints)
    3. Project allow-list
    4. Health status & cooldown for degraded providers
    5. Capability requirements (structured output, tool calling, context length)
- Scoring & ranking:
    Calculates composite score based on task specificity, local vs cloud preference,
    and priority.
- Fallback chain:
    Returns primary choice along with an ordered list of fallback candidates and
    an audit trail of rejected providers with explicit reasons.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from core.capability_registry import CapabilityRegistry, registry as default_registry
from providers.base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)


@dataclass
class RejectedCandidate:
    provider_id: str
    model_id: str
    display_name: str
    reason: str


@dataclass
class RoutingCandidate:
    provider_id: str
    model_id: str
    display_name: str
    capability: ProviderCapability
    provider: BaseProvider
    score: float
    reason: str


@dataclass
class RoutingResult:
    selected_provider_id: str
    selected_model_id: str
    selected_provider: BaseProvider
    selected_capability: ProviderCapability
    selection_reason: str
    score: float
    fallback_candidates: List[RoutingCandidate] = field(default_factory=list)
    rejected_candidates: List[RejectedCandidate] = field(default_factory=list)


# Domain-specific specialist rankings:
# Mapping of task_type -> priority ranking of (provider_id, model_pattern, specialist_bonus)
TASK_DOMAIN_SPECIALISTS: Dict[str, List[tuple[str, str, float]]] = {
    "code": [
        ("groq", "qwen3.8-27b", 35.0),              # Ultra-fast open coding specialist on LPU
        ("mistral", "codestral-latest", 30.0),      # Dedicated coding model
        ("gemini", "gemini-3.8-flash", 25.0),       # High-capacity cloud reasoning
        ("groq", "openai/gpt-oss-120b", 25.0),      # 120B reasoning
        ("huggingface", "mistralai/Mistral-7B-Instruct-v0.3", 15.0),
        ("ollama", "qwen2.5-coder", 20.0),          # Local coder if present
        ("ollama", "llama3.2", 5.0),                # Generic fallback
    ],
    "research": [
        ("gemini", "gemini-3.8-flash", 35.0),       # 1M token context window & web synthesis
        ("gemini", "gemini-1.5-flash", 35.0),       # Backward compatibility alias
        ("groq", "openai/gpt-oss-120b", 28.0),      # 120B knowledge base
        ("groq", "qwen3.8-27b", 22.0),
        ("mistral", "mistral-large-latest", 25.0),
        ("ollama", "llama3.2", 5.0),
    ],
    "analyze": [
        ("groq", "openai/gpt-oss-120b", 35.0),      # Frontier 120B reasoning specialist
        ("gemini", "gemini-3.8-flash", 30.0),
        ("groq", "qwen3.8-27b", 25.0),
        ("mistral", "mistral-large-latest", 25.0),
        ("ollama", "llama3.2", 10.0),
    ],
    "write": [
        ("gemini", "gemini-3.8-flash", 35.0),       # High-cohesion long-form writing & documentation
        ("gemini", "gemini-1.5-flash", 35.0),       # Backward compatibility alias
        ("groq", "openai/gpt-oss-120b", 28.0),      # 120B writing
        ("groq", "qwen3.8-27b", 20.0),
        ("mistral", "mistral-large-latest", 25.0),
        ("ollama", "llama3.2", 10.0),
    ],
    "plan": [
        ("groq", "openai/gpt-oss-120b", 35.0),      # Multi-step strategic planning (120B)
        ("gemini", "gemini-3.8-flash", 30.0),
        ("groq", "qwen3.8-27b", 25.0),
        ("ollama", "llama3.2", 15.0),               # Fast local planning
    ],
    "general": [
        ("ollama", "llama3.2", 25.0),               # Fast zero-cost local execution
        ("groq", "openai/gpt-oss-120b", 20.0),
        ("gemini", "gemini-3.8-flash", 15.0),
    ],
}


class HealthTracker:
    """
    In-memory health and degradation tracker.
    Provides cooldown periods when providers experience repeated or non-retryable failures.
    """

    def __init__(self, cooldown_seconds: int = 180):
        self.cooldown_seconds = cooldown_seconds
        # Key: "{provider_id}:{model_id}" -> timestamp until which it is degraded
        self._degraded_until: Dict[str, float] = {}
        # Key: "{provider_id}:{model_id}" -> (is_healthy, last_check_time)
        self._health_cache: Dict[str, tuple[bool, float]] = {}
        self.cache_ttl = 30.0

    def mark_degraded(self, provider_id: str, model_id: str, duration: Optional[int] = None) -> None:
        key = f"{provider_id}:{model_id}"
        cooldown = duration if duration is not None else self.cooldown_seconds
        self._degraded_until[key] = time.time() + cooldown
        logger.warning("Provider %s marked degraded for %ss", key, cooldown)

    def is_degraded(self, provider_id: str, model_id: str) -> bool:
        key = f"{provider_id}:{model_id}"
        until = self._degraded_until.get(key, 0.0)
        return time.time() < until

    def clear_degradation(self, provider_id: str, model_id: str) -> None:
        key = f"{provider_id}:{model_id}"
        self._degraded_until.pop(key, None)

    async def check_health(self, provider: BaseProvider, force: bool = False) -> bool:
        cap = provider.get_capability()
        key = f"{cap.provider_id}:{cap.model_id}"
        now = time.time()

        if self.is_degraded(cap.provider_id, cap.model_id):
            return False

        if not force and key in self._health_cache:
            is_healthy, cached_at = self._health_cache[key]
            if now - cached_at < self.cache_ttl:
                return is_healthy

        try:
            is_healthy = await provider.health_check()
        except Exception as exc:
            logger.warning("Health check failed for %s: %s", key, exc)
            is_healthy = False

        self._health_cache[key] = (is_healthy, now)
        return is_healthy


# Global health tracker instance
health_tracker = HealthTracker()


class Router:
    """
    Deterministic Router selecting optimal AI model for a task.
    """

    def __init__(
        self,
        registry: CapabilityRegistry = default_registry,
        health: HealthTracker = health_tracker,
    ):
        self.registry = registry
        self.health = health

    async def route(
        self,
        task_type: str,
        task_priority: int = 5,
        allowed_providers: Optional[List[str]] = None,
        prefer_local: bool = True,
        requires_structured_output: bool = False,
        requires_tool_calling: bool = False,
        min_context_tokens: int = 0,
        user_override_provider: Optional[str] = None,
        user_override_model: Optional[str] = None,
    ) -> RoutingResult:
        """
        Route a task to the most appropriate AI provider.
        """
        all_caps = self.registry.list_all_capabilities()
        rejected: List[RejectedCandidate] = []
        eligible: List[RoutingCandidate] = []

        # If user explicitly specifies an override provider and model
        if user_override_provider and user_override_model:
            provider = self.registry.get_provider(user_override_provider, user_override_model)
            cap = self.registry.get_capability(user_override_provider, user_override_model)
            if provider and cap:
                is_healthy = await self.health.check_health(provider)
                if is_healthy:
                    return RoutingResult(
                        selected_provider_id=user_override_provider,
                        selected_model_id=user_override_model,
                        selected_provider=provider,
                        selected_capability=cap,
                        selection_reason=f"User override requested: {cap.display_name}",
                        score=100.0,
                    )
                else:
                    rejected.append(
                        RejectedCandidate(
                            provider_id=user_override_provider,
                            model_id=user_override_model,
                            display_name=cap.display_name,
                            reason="User-specified override failed health check or is degraded",
                        )
                    )
        elif user_override_provider and not user_override_model:
            allowed_providers = [user_override_provider]

        for cap in all_caps:
            key = f"{cap.provider_id}:{cap.model_id}"
            provider = self.registry.get_provider(cap.provider_id, cap.model_id)
            if not provider:
                continue

            # 1. Enabled check
            if not cap.is_enabled:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason="Provider is disabled in registry",
                    )
                )
                continue

            # 2. Configured check
            if not cap.is_configured:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason=f"Provider is not configured (missing {cap.api_key_env_var or 'credentials'})",
                    )
                )
                continue

            # 3. Project allow-list
            if allowed_providers and cap.provider_id not in allowed_providers:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason=f"Provider {cap.provider_id} not in project allowed list",
                    )
                )
                continue

            # 4. Task type support
            supports_task = (
                task_type in cap.supported_task_types or "general" in cap.supported_task_types
            )
            if not supports_task:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason=f"Task type '{task_type}' not supported (supported: {cap.supported_task_types})",
                    )
                )
                continue

            # 5. Feature requirements
            if requires_structured_output and not cap.supports_structured_output:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason="Structured output required but unsupported",
                    )
                )
                continue

            if requires_tool_calling and not cap.supports_tool_calling:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason="Tool calling required but unsupported",
                    )
                )
                continue

            if min_context_tokens > 0 and cap.context_window_tokens < min_context_tokens:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason=f"Context window ({cap.context_window_tokens}) smaller than required ({min_context_tokens})",
                    )
                )
                continue

            # 6. Degraded / Health check
            if self.health.is_degraded(cap.provider_id, cap.model_id):
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason="Provider is in cooldown degradation state after recent failures",
                    )
                )
                continue

            is_healthy = await self.health.check_health(provider)
            if not is_healthy:
                rejected.append(
                    RejectedCandidate(
                        provider_id=cap.provider_id,
                        model_id=cap.model_id,
                        display_name=cap.display_name,
                        reason="Failed runtime health check",
                    )
                )
                continue

            # 7. Scoring
            # Base score
            score = 50.0

            # Exact task match vs fallback to "general"
            if task_type in cap.supported_task_types:
                score += 15.0
            elif "general" in cap.supported_task_types:
                score += 5.0

            # Domain Specialist Bonus — prioritize specialized models for their expert tasks
            specialist_bonus = 0.0
            specialist_specs = TASK_DOMAIN_SPECIALISTS.get(task_type, [])
            for p_id, m_pattern, bonus in specialist_specs:
                if cap.provider_id == p_id and (m_pattern in cap.model_id or m_pattern == "*"):
                    specialist_bonus = max(specialist_bonus, bonus)
                    break
            score += specialist_bonus

            # Local preference (tie-breaker for comparable candidates, not overriding domain experts)
            if prefer_local and cap.is_local:
                score += 8.0
            elif not prefer_local and not cap.is_local:
                score += 8.0

            # Priority / capacity: large context models get bonus for large context tasks
            if cap.context_window_tokens >= 32000:
                score += 5.0

            reason_desc = (
                f"Domain specialist '{cap.display_name}' for '{task_type}' "
                f"(match={task_type in cap.supported_task_types}, bonus=+{specialist_bonus:.0f}, score={score:.1f})"
            )

            eligible.append(
                RoutingCandidate(
                    provider_id=cap.provider_id,
                    model_id=cap.model_id,
                    display_name=cap.display_name,
                    capability=cap,
                    provider=provider,
                    score=score,
                    reason=reason_desc,
                )
            )

        if not eligible:
            reasons_summary = "; ".join(f"{r.display_name}: {r.reason}" for r in rejected[:3])
            raise RuntimeError(
                f"No eligible AI providers available for task type '{task_type}'. "
                f"Evaluated {len(rejected)} providers: {reasons_summary}"
            )

        # Sort eligible by score descending
        eligible.sort(key=lambda c: c.score, reverse=True)
        winner = eligible[0]
        fallbacks = eligible[1:]

        return RoutingResult(
            selected_provider_id=winner.provider_id,
            selected_model_id=winner.model_id,
            selected_provider=winner.provider,
            selected_capability=winner.capability,
            selection_reason=winner.reason,
            score=winner.score,
            fallback_candidates=fallbacks,
            rejected_candidates=rejected,
        )


router = Router()
