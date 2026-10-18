"""
BaseProvider — Common interface for all AI providers (local and cloud).

Every provider (Ollama, Gemini, Bedrock, etc.) must implement this interface.
The planner, router, coordinator, and memory service interact ONLY through
this interface — never with provider-specific code directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


# ── Request / Response schemas ────────────────────────────────────────────────

@dataclass
class ProviderRequest:
    """
    Normalized input sent to any provider.
    The coordinator builds this from the task + context package.
    """
    task_id: str
    task_type: str                          # "code" | "research" | "write" | "analyze" | "plan" | "general"
    system_prompt: str
    user_message: str
    context: dict = field(default_factory=dict)  # Structured context from memory
    structured_output_schema: Optional[dict] = None
    tools: Optional[list] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False


@dataclass
class ProviderResponse:
    """
    Normalized output from any provider.
    """
    provider_id: str
    model_id: str
    content: str                            # Main text output
    structured_output: Optional[dict] = None
    tool_calls: Optional[list] = None
    finish_reason: str = "stop"            # "stop" | "length" | "tool_calls" | "error"
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_estimate_usd: Optional[float] = None
    raw_response: Any = None               # Provider-specific; only for debugging


@dataclass
class ProviderError(Exception):
    """
    Normalized error from any provider.
    is_retryable: True means the coordinator can retry with same or different provider.
    """
    error_type: str                        # "rate_limit" | "auth" | "model_unavailable" | "timeout" | "content_filter" | "unknown"
    message: str
    is_retryable: bool
    retry_after_seconds: Optional[int] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None

    def __str__(self) -> str:
        return f"[{self.error_type}] {self.message}"


@dataclass
class ProviderCapability:
    """
    Static capability descriptor for a specific provider+model combination.
    This is the source of truth for what the provider CAN do —
    not what it is currently doing (that's HealthService).
    """
    provider_id: str
    model_id: str
    display_name: str

    # Verified capabilities
    supported_task_types: list[str] = field(default_factory=lambda: ["general"])
    input_modalities: list[str] = field(default_factory=lambda: ["text"])
    output_modalities: list[str] = field(default_factory=lambda: ["text"])
    context_window_tokens: int = 4096
    max_output_tokens: int = 2048
    supports_structured_output: bool = False
    supports_tool_calling: bool = False
    supports_streaming: bool = False

    # Configuration metadata
    requires_api_key: bool = True
    api_key_env_var: Optional[str] = None
    base_url: Optional[str] = None
    is_local: bool = False
    is_configured: bool = False
    is_enabled: bool = True

    # Trust level for capability claims
    capability_source: str = "official_docs"  # "official_docs" | "tested" | "assumed"


# ── Abstract Base ─────────────────────────────────────────────────────────────

class BaseProvider(ABC):
    """
    Abstract base class for all AI providers.
    Subclasses must implement: execute, stream, health_check, get_capability.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider (e.g., 'ollama', 'gemini')."""
        ...

    @abstractmethod
    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """
        Execute a task synchronously and return the full response.
        Raises ProviderError on failure.
        """
        ...

    @abstractmethod
    def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """
        Stream response tokens as an async generator.
        Raises ProviderError on failure.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the provider is reachable and configured.
        Returns True if healthy.
        Should be fast — used by router before assignment.
        """
        ...

    @abstractmethod
    def get_capability(self) -> ProviderCapability:
        """
        Return the static capability descriptor for this provider+model.
        Must not make any network calls.
        """
        ...

    async def execute_with_retry(
        self,
        request: ProviderRequest,
        max_retries: int = 2,
    ) -> ProviderResponse:
        """
        Wraps execute() with exponential backoff for retryable errors.
        Non-retryable errors are re-raised immediately.
        """
        import asyncio

        last_error: Optional[ProviderError] = None

        for attempt in range(max_retries + 1):
            try:
                return await self.execute(request)
            except ProviderError as e:
                last_error = e
                if not e.is_retryable or attempt >= max_retries:
                    raise

                wait = e.retry_after_seconds if e.retry_after_seconds else (2 ** attempt)
                await asyncio.sleep(wait)

        raise last_error  # type: ignore
