"""
Mock Provider — for testing without real AI connections.
Returns deterministic responses for any prompt.
"""

from typing import AsyncIterator, Optional
from providers.base import BaseProvider, ProviderCapability, ProviderRequest, ProviderResponse


class MockProvider(BaseProvider):
    """
    A fake provider that returns predictable responses.
    Used in unit and integration tests.
    Never makes network calls.
    """

    def __init__(
        self,
        provider_id: str = "mock",
        model_id: str = "mock-model",
        response_content: str = "Mock response content.",
        should_fail: bool = False,
        is_configured: bool = True,
        supported_task_types: Optional[list[str]] = None,
        is_local: bool = True,
        fail_execution_only: bool = False,
    ):
        self._provider_id = provider_id
        self._model_id = model_id
        self._response_content = response_content
        self._should_fail = should_fail
        self._fail_execution_only = fail_execution_only
        self._is_configured = is_configured
        self._supported_task_types = supported_task_types or [
            "code", "research", "write", "analyze", "plan", "general"
        ]
        self._is_local = is_local
        self.call_count = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def get_capability(self) -> ProviderCapability:
        return ProviderCapability(
            provider_id=self._provider_id,
            model_id=self._model_id,
            display_name=f"Mock Provider ({self._model_id})",
            supported_task_types=self._supported_task_types,
            input_modalities=["text"],
            output_modalities=["text"],
            context_window_tokens=128_000,
            max_output_tokens=4096,
            supports_structured_output=True,
            supports_tool_calling=True,
            supports_streaming=True,
            requires_api_key=False,
            is_local=self._is_local,
            is_configured=self._is_configured,
            is_enabled=True,
            capability_source="tested",
        )

    async def health_check(self) -> bool:
        if self._fail_execution_only:
            return True
        return not self._should_fail

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        from providers.base import ProviderError
        self.call_count += 1
        if self._should_fail or self._fail_execution_only:
            raise ProviderError(
                error_type="model_unavailable",
                message="Mock provider configured to fail.",
                is_retryable=self._should_fail,
                provider_id=self._provider_id,
                model_id=self._model_id,
            )
        return ProviderResponse(
            provider_id=self._provider_id,
            model_id=self._model_id,
            content=self._response_content,
            finish_reason="stop",
            tokens_input=len(request.user_message.split()),
            tokens_output=len(self._response_content.split()),
            cost_estimate_usd=0.0,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        from providers.base import ProviderError
        self.call_count += 1
        if self._should_fail or self._fail_execution_only:
            raise ProviderError(
                error_type="model_unavailable",
                message="Mock provider configured to fail during stream.",
                is_retryable=False,
                provider_id=self._provider_id,
                model_id=self._model_id,
            )
        for word in self._response_content.split():
            yield word + " "
