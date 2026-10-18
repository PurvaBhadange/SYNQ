"""
Unit tests for Deterministic Router.
Tests multi-stage filtering, scoring, health degradation, user overrides, and fallback generation.
No external network calls made.
"""

import pytest
from core.capability_registry import CapabilityRegistry
from core.router import HealthTracker, Router
from tests.mocks.mock_provider import MockProvider


@pytest.fixture
def mock_registry():
    reg = CapabilityRegistry()
    # Code specialist
    code_provider = MockProvider(
        provider_id="ollama",
        model_id="qwen2.5-coder",
        supported_task_types=["code", "general"],
        is_local=True,
    )
    # Research specialist
    research_provider = MockProvider(
        provider_id="gemini",
        model_id="gemini-1.5-flash",
        supported_task_types=["research", "write", "general"],
        is_local=False,
    )
    # General model
    general_provider = MockProvider(
        provider_id="ollama",
        model_id="llama3.2",
        supported_task_types=["general"],
        is_local=True,
    )

    reg.register_provider(code_provider)
    reg.register_provider(research_provider)
    reg.register_provider(general_provider)
    return reg


@pytest.fixture
def health():
    return HealthTracker(cooldown_seconds=60)


@pytest.mark.asyncio
async def test_route_selects_exact_task_match(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    res = await router.route(task_type="code")

    assert res.selected_provider_id == "ollama"
    assert res.selected_model_id == "qwen2.5-coder"
    assert len(res.fallback_candidates) >= 1
    assert "code" in res.selection_reason.lower()


@pytest.mark.asyncio
async def test_route_research_task(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    res = await router.route(task_type="research", prefer_local=False)

    assert res.selected_provider_id == "gemini"
    assert res.selected_model_id == "gemini-1.5-flash"


@pytest.mark.asyncio
async def test_route_respects_project_allow_list(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    # Even though gemini supports research, if project only allows ollama:
    res = await router.route(task_type="research", allowed_providers=["ollama"])

    # Falls back to general Ollama model that supports "general"
    assert res.selected_provider_id == "ollama"
    # Gemini should be in rejected list
    gemini_rejected = any(r.provider_id == "gemini" for r in res.rejected_candidates)
    assert gemini_rejected


@pytest.mark.asyncio
async def test_route_handles_degradation_and_fallback(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    # Mark the primary coder degraded
    health.mark_degraded("ollama", "qwen2.5-coder")

    # Routing for code should now skip qwen2.5-coder and pick the next best model (e.g. llama3.2 general)
    res = await router.route(task_type="code")
    assert res.selected_model_id != "qwen2.5-coder"
    assert any(r.model_id == "qwen2.5-coder" for r in res.rejected_candidates)


@pytest.mark.asyncio
async def test_route_user_override(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    res = await router.route(
        task_type="code",
        user_override_provider="gemini",
        user_override_model="gemini-1.5-flash",
    )
    assert res.selected_provider_id == "gemini"
    assert res.selected_model_id == "gemini-1.5-flash"
    assert "User override" in res.selection_reason


@pytest.mark.asyncio
async def test_route_user_override_provider_only(mock_registry, health):
    router = Router(registry=mock_registry, health=health)
    res = await router.route(
        task_type="code",
        user_override_provider="gemini",
    )
    assert res.selected_provider_id == "gemini"

