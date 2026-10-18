"""
Unit tests for the BaseProvider interface and ProviderError.
These tests do NOT make network calls.
"""

import pytest
from providers.base import ProviderCapability, ProviderError, ProviderRequest, ProviderResponse


class TestProviderError:
    def test_str_representation(self):
        err = ProviderError(
            error_type="rate_limit",
            message="Too many requests",
            is_retryable=True,
            retry_after_seconds=60,
        )
        assert "rate_limit" in str(err)
        assert "Too many requests" in str(err)

    def test_non_retryable(self):
        err = ProviderError(
            error_type="auth",
            message="Invalid API key",
            is_retryable=False,
        )
        assert err.is_retryable is False
        assert err.retry_after_seconds is None


class TestProviderCapability:
    def test_default_values(self):
        cap = ProviderCapability(
            provider_id="test",
            model_id="test-model",
            display_name="Test Model",
        )
        assert cap.is_configured is False
        assert cap.supports_streaming is False
        assert "general" in cap.supported_task_types

    def test_local_provider_no_key_required(self):
        cap = ProviderCapability(
            provider_id="ollama",
            model_id="llama3.2",
            display_name="Ollama llama3.2",
            requires_api_key=False,
            is_local=True,
            is_configured=True,  # Always configured — no key needed
        )
        assert cap.requires_api_key is False
        assert cap.is_local is True
        assert cap.is_configured is True


class TestProviderRequest:
    def test_defaults(self):
        req = ProviderRequest(
            task_id="task-123",
            task_type="code",
            system_prompt="You are a coding assistant.",
            user_message="Write a hello world in Python.",
        )
        assert req.max_tokens == 4096
        assert req.temperature == 0.7
        assert req.stream is False
        assert req.context == {}
        assert req.tools is None


class TestMockProvider:
    """Tests using the MockProvider to verify BaseProvider contract."""

    @pytest.fixture
    def mock_provider(self):
        import sys
        sys.path.insert(0, ".")
        from tests.mocks.mock_provider import MockProvider
        return MockProvider()

    @pytest.fixture
    def failing_mock(self):
        from tests.mocks.mock_provider import MockProvider
        return MockProvider(should_fail=True)

    def test_capability_returns_data(self, mock_provider):
        cap = mock_provider.get_capability()
        assert cap.provider_id == "mock"
        assert cap.is_configured is True
        assert len(cap.supported_task_types) > 0

    @pytest.mark.asyncio
    async def test_execute_returns_response(self, mock_provider):
        req = ProviderRequest(
            task_id="t1",
            task_type="general",
            system_prompt="",
            user_message="Hello",
        )
        resp = await mock_provider.execute(req)
        assert isinstance(resp, ProviderResponse)
        assert resp.provider_id == "mock"
        assert resp.content
        assert mock_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, mock_provider):
        assert await mock_provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, failing_mock):
        assert await failing_mock.health_check() is False

    @pytest.mark.asyncio
    async def test_execute_raises_on_failure(self, failing_mock):
        req = ProviderRequest(
            task_id="t2",
            task_type="general",
            system_prompt="",
            user_message="Hello",
        )
        with pytest.raises(ProviderError) as exc_info:
            await failing_mock.execute(req)
        assert exc_info.value.error_type == "model_unavailable"
        assert exc_info.value.is_retryable is True

    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self, mock_provider):
        req = ProviderRequest(
            task_id="t3",
            task_type="general",
            system_prompt="",
            user_message="Hello",
        )
        tokens = []
        async for token in mock_provider.stream(req):
            tokens.append(token)
        assert len(tokens) > 0
        assert "".join(tokens).strip() == mock_provider._response_content

    @pytest.mark.asyncio
    async def test_execute_with_retry_gives_up_on_non_retryable(self):
        from tests.mocks.mock_provider import MockProvider
        from providers.base import ProviderError as PE

        class NonRetryableMock(MockProvider):
            async def execute(self, request):
                raise PE(
                    error_type="auth",
                    message="auth failed",
                    is_retryable=False,
                )

        provider = NonRetryableMock()
        req = ProviderRequest(
            task_id="t4", task_type="general",
            system_prompt="", user_message="hello"
        )
        with pytest.raises(PE) as exc_info:
            await provider.execute_with_retry(req, max_retries=3)
        # Should have only been called once (no retry on non-retryable)
        assert exc_info.value.error_type == "auth"
