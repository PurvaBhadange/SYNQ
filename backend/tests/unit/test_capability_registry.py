"""
Unit tests for the Capability Registry.
No network calls — uses MockProvider only.
"""

import pytest
from core.capability_registry import CapabilityRegistry
from tests.mocks.mock_provider import MockProvider


@pytest.fixture
def fresh_registry():
    """Return a fresh (empty) CapabilityRegistry for each test."""
    return CapabilityRegistry()


@pytest.fixture
def populated_registry():
    """Registry pre-populated with mock providers."""
    reg = CapabilityRegistry()
    reg.register_provider(MockProvider("ollama", "llama3.2"))
    reg.register_provider(MockProvider("gemini", "gemini-1.5-flash"))
    return reg


class TestCapabilityRegistry:

    def test_register_and_retrieve(self, fresh_registry):
        provider = MockProvider("ollama", "llama3.2")
        fresh_registry.register_provider(provider)
        retrieved = fresh_registry.get_provider("ollama", "llama3.2")
        assert retrieved is provider

    def test_get_nonexistent_provider_returns_none(self, fresh_registry):
        result = fresh_registry.get_provider("nonexistent", "model")
        assert result is None

    def test_list_all_capabilities(self, populated_registry):
        caps = populated_registry.list_all_capabilities()
        assert len(caps) == 2
        provider_ids = {c.provider_id for c in caps}
        assert "ollama" in provider_ids
        assert "gemini" in provider_ids

    def test_get_eligible_all_configured(self, populated_registry):
        eligible = populated_registry.get_eligible_providers(task_type="general")
        assert len(eligible) == 2

    def test_filter_by_task_type(self, fresh_registry):
        """Providers with only specific task types should be filtered correctly."""
        from providers.base import ProviderCapability

        class CodeOnlyMock(MockProvider):
            def get_capability(self):
                cap = super().get_capability()
                cap.supported_task_types = ["code"]
                return cap

        fresh_registry.register_provider(MockProvider("all", "general-model"))  # supports "general"
        fresh_registry.register_provider(CodeOnlyMock("code-only", "code-model"))

        # Asking for "research" — code-only should be excluded
        # general supports "general" but not "research" — depends on mock
        eligible = fresh_registry.get_eligible_providers(task_type="code")
        provider_ids = {cap.provider_id for cap, _ in eligible}
        # code-only explicitly supports code; "all" also supports code via mock
        assert "code-only" in provider_ids

    def test_filter_unconfigured_providers(self, fresh_registry):
        """Unconfigured providers should not appear in eligible list."""
        fresh_registry.register_provider(
            MockProvider("cloud", "gpt4", is_configured=False)
        )
        fresh_registry.register_provider(
            MockProvider("local", "llama3", is_configured=True)
        )
        eligible = fresh_registry.get_eligible_providers(task_type="general")
        provider_ids = {cap.provider_id for cap, _ in eligible}
        assert "cloud" not in provider_ids
        assert "local" in provider_ids

    def test_allowed_provider_filter(self, populated_registry):
        """Project allow-list should restrict routing."""
        eligible = populated_registry.get_eligible_providers(
            task_type="general",
            allowed_provider_ids=["ollama"],
        )
        assert all(cap.provider_id == "ollama" for cap, _ in eligible)

    def test_update_configuration_status(self, populated_registry):
        populated_registry.update_configuration_status("gemini", "gemini-1.5-flash", False)
        cap = populated_registry.get_capability("gemini", "gemini-1.5-flash")
        assert cap.is_configured is False

    def test_summary_structure(self, populated_registry):
        summary = populated_registry.summary()
        assert "total_registered" in summary
        assert "configured" in summary
        assert "providers" in summary
        assert summary["total_registered"] == 2
