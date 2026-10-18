"""
Capability Registry
Central registry for all known AI providers and their verified capabilities.

Design principles:
- Capabilities are STATIC (what the provider CAN do, from official docs).
- Health is DYNAMIC (checked live, not stored here).
- User preferences are SEPARATE (stored in DB).
- Router uses this registry to find eligible providers for a task.
"""

import logging
from typing import Optional

from providers.base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)


_MODEL_ALIASES: dict[str, dict[str, str]] = {
    "gemini": {
        "gemini-1.5-flash": "gemini-3.8-flash",
        "gemini-2.5-flash": "gemini-3.8-flash",
        "gemini-1.5-pro": "gemini-3.8-flash",
    },
    "groq": {
        "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
        "mixtral-8x7b-32768": "qwen/qwen3.8-27b",
        "llama-3.1-70b-versatile": "openai/gpt-oss-120b",
        "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    },
}


class CapabilityRegistry:
    """
    In-memory registry of registered providers and their capabilities.
    Populated on application startup via register_provider().
    Persisted to DB via sync_to_db() for UI display and recovery.
    """

    def __init__(self):
        # Key: "{provider_id}:{model_id}" → ProviderCapability
        self._capabilities: dict[str, ProviderCapability] = {}
        # Key: "{provider_id}:{model_id}" → BaseProvider instance
        self._providers: dict[str, BaseProvider] = {}

    def register_provider(self, provider: BaseProvider) -> None:
        """Register a provider instance and store its capability descriptor."""
        cap = provider.get_capability()
        key = f"{cap.provider_id}:{cap.model_id}"
        self._capabilities[key] = cap
        self._providers[key] = provider
        logger.info(
            "Registered provider: %s | tasks=%s | local=%s | configured=%s",
            cap.display_name,
            cap.supported_task_types,
            cap.is_local,
            cap.is_configured,
        )

    def get_provider(self, provider_id: str, model_id: str) -> Optional[BaseProvider]:
        """Return the provider instance for a specific provider+model, resolving aliases."""
        key = f"{provider_id}:{model_id}"
        if key in self._providers:
            return self._providers[key]
        resolved = _MODEL_ALIASES.get(provider_id, {}).get(model_id)
        if resolved and f"{provider_id}:{resolved}" in self._providers:
            return self._providers[f"{provider_id}:{resolved}"]
        candidates = [p for k, p in self._providers.items() if k.startswith(f"{provider_id}:")]
        return candidates[0] if candidates else None

    def get_capability(self, provider_id: str, model_id: str) -> Optional[ProviderCapability]:
        """Return the capability descriptor for a specific provider+model, resolving aliases."""
        key = f"{provider_id}:{model_id}"
        if key in self._capabilities:
            return self._capabilities[key]
        resolved = _MODEL_ALIASES.get(provider_id, {}).get(model_id)
        if resolved and f"{provider_id}:{resolved}" in self._capabilities:
            return self._capabilities[f"{provider_id}:{resolved}"]
        candidates = [c for k, c in self._capabilities.items() if k.startswith(f"{provider_id}:")]
        return candidates[0] if candidates else None

    def list_all_capabilities(self) -> list[ProviderCapability]:
        """Return all registered capabilities."""
        return list(self._capabilities.values())

    def list_all_providers(self) -> list[BaseProvider]:
        """Return all registered provider instances."""
        return list(self._providers.values())

    def get_eligible_providers(
        self,
        task_type: str,
        requires_structured_output: bool = False,
        requires_tool_calling: bool = False,
        min_context_tokens: int = 0,
        allowed_provider_ids: Optional[list[str]] = None,
    ) -> list[tuple[ProviderCapability, BaseProvider]]:
        """
        Return (capability, provider) pairs that meet the given requirements.
        Only returns configured and enabled providers.
        Results are NOT health-checked here — router does that.
        """
        results = []
        for key, cap in self._capabilities.items():
            # Must be enabled and configured
            if not cap.is_enabled or not cap.is_configured:
                continue

            # Must support the task type
            if task_type not in cap.supported_task_types and "general" not in cap.supported_task_types:
                continue

            # Structured output requirement
            if requires_structured_output and not cap.supports_structured_output:
                continue

            # Tool calling requirement
            if requires_tool_calling and not cap.supports_tool_calling:
                continue

            # Context window requirement
            if min_context_tokens > cap.context_window_tokens:
                continue

            # Project allow-list filter
            if allowed_provider_ids and cap.provider_id not in allowed_provider_ids:
                continue

            provider = self._providers.get(key)
            if provider:
                results.append((cap, provider))

        return results

    def update_configuration_status(
        self, provider_id: str, model_id: str, is_configured: bool
    ) -> None:
        """Update the is_configured flag (called when API key becomes available/unavailable)."""
        key = f"{provider_id}:{model_id}"
        if key in self._capabilities:
            self._capabilities[key].is_configured = is_configured

    def summary(self) -> dict:
        """Return a summary for health/status endpoints."""
        caps = self.list_all_capabilities()
        return {
            "total_registered": len(caps),
            "configured": sum(1 for c in caps if c.is_configured),
            "local": sum(1 for c in caps if c.is_local),
            "cloud": sum(1 for c in caps if not c.is_local),
            "providers": [
                {
                    "key": f"{c.provider_id}:{c.model_id}",
                    "display_name": c.display_name,
                    "is_local": c.is_local,
                    "is_configured": c.is_configured,
                    "is_enabled": c.is_enabled,
                    "task_types": c.supported_task_types,
                }
                for c in caps
            ],
        }


# Singleton registry instance — imported by router, coordinator, and startup.
registry = CapabilityRegistry()
