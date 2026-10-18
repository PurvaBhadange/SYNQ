"""
Ollama Provider
Implements BaseProvider for local Ollama LLM inference.
Communicates with Ollama's HTTP API (no API key required).
"""

import json
import logging
from typing import AsyncIterator, Optional

import httpx

from providers.base import (
    BaseProvider,
    ProviderCapability,
    ProviderError,
    ProviderRequest,
    ProviderResponse,
)
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Known capabilities for common Ollama models.
# Expand as more models are tested.
_MODEL_CAPABILITIES: dict[str, dict] = {
    "llama3.2": {
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "context_window_tokens": 128_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "llama3.2:3b": {
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "context_window_tokens": 128_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "llama3.2:latest": {
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "context_window_tokens": 128_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "llama3.2:1b": {
        "supported_task_types": ["write", "general", "analyze"],
        "context_window_tokens": 128_000,
        "max_output_tokens": 4096,
        "supports_structured_output": False,
        "supports_tool_calling": False,
        "supports_streaming": True,
    },
    "qwen2.5-coder:7b": {
        "supported_task_types": ["code", "analyze", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "mistral": {
        "supported_task_types": ["code", "analyze", "write", "research", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "mistral:7b": {
        "supported_task_types": ["code", "analyze", "write", "research", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
}

_DEFAULT_CAPABILITY = {
    "supported_task_types": ["general"],
    "context_window_tokens": 8192,
    "max_output_tokens": 4096,
    "supports_structured_output": False,
    "supports_tool_calling": False,
    "supports_streaming": True,
}


class OllamaProvider(BaseProvider):
    """
    Provider for locally-running Ollama models.
    Each instance represents one model running under Ollama.
    """

    def __init__(self, model_id: str, base_url: Optional[str] = None):
        self._model_id = model_id
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self._model_id

    def get_capability(self) -> ProviderCapability:
        base_name = self._model_id.split(":")[0]
        cap = _MODEL_CAPABILITIES.get(self._model_id) or _MODEL_CAPABILITIES.get(base_name) or _DEFAULT_CAPABILITY
        return ProviderCapability(
            provider_id="ollama",
            model_id=self._model_id,
            display_name=f"Ollama / {self._model_id}",
            supported_task_types=cap["supported_task_types"],
            input_modalities=["text"],
            output_modalities=["text"],
            context_window_tokens=cap["context_window_tokens"],
            max_output_tokens=cap["max_output_tokens"],
            supports_structured_output=cap["supports_structured_output"],
            supports_tool_calling=cap["supports_tool_calling"],
            supports_streaming=cap["supports_streaming"],
            requires_api_key=False,
            api_key_env_var=None,
            base_url=self._base_url,
            is_local=True,
            is_configured=True,   # Always configured — no key needed
            is_enabled=settings.enable_ollama,
            capability_source="tested",
        )

    async def _resolve_model_id(self) -> str:
        """Resolve model name to an exact tag available in Ollama (e.g. llama3.2 -> llama3.2:3b)."""
        try:
            resp = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if self._model_id in model_names:
                    return self._model_id
                # Check prefix/base matching (e.g. llama3.2 matches llama3.2:3b or llama3.2:latest)
                base_id = self._model_id.split(":")[0]
                for name in model_names:
                    if name.split(":")[0] == base_id or name.startswith(self._model_id):
                        return name
        except Exception:
            pass
        return self._model_id

    async def health_check(self) -> bool:
        """
        Check Ollama is running by calling its version endpoint.
        Also verify the specific model (or a compatible tag) is available.
        """
        try:
            resp = await self._client.get(f"{self._base_url}/api/version", timeout=5.0)
            if resp.status_code != 200:
                return False
            # Check model is pulled
            tags_resp = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            if tags_resp.status_code != 200:
                return False
            models = tags_resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            base_id = self._model_id.split(":")[0]
            available = any(
                self._model_id == name
                or self._model_id in name
                or base_id == name.split(":")[0]
                for name in model_names
            )
            if not available:
                logger.warning(
                    "Ollama is running but model '%s' is not pulled. Available: %s. Run: ollama pull %s",
                    self._model_id,
                    model_names,
                    self._model_id,
                )
                return False
            return True
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.debug("Ollama health check failed: %s", e)
            return False

    async def check_model_available(self) -> bool:
        """Returns True if the specific model is pulled and ready."""
        try:
            resp = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            models = resp.json().get("models", [])
            base_id = self._model_id.split(":")[0]
            return any(
                self._model_id in m.get("name", "") or base_id == m.get("name", "").split(":")[0]
                for m in models
            )
        except Exception:
            return False

    def _build_messages(self, request: ProviderRequest) -> list[dict]:
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        # Inject context into user message if provided
        if request.context:
            context_block = json.dumps(request.context, indent=2)
            user_content = (
                f"<context>\n{context_block}\n</context>\n\n{request.user_message}"
            )
        else:
            user_content = request.user_message

        messages.append({"role": "user", "content": user_content})
        return messages

    def _build_payload(self, request: ProviderRequest, stream: bool, resolved_model: Optional[str] = None) -> dict:
        payload: dict = {
            "model": resolved_model or self._model_id,
            "messages": self._build_messages(request),
            "stream": stream,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        # Request structured JSON output if schema provided
        if request.structured_output_schema:
            payload["format"] = "json"
        return payload

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        resolved_model = await self._resolve_model_id()
        payload = self._build_payload(request, stream=False, resolved_model=resolved_model)
        try:
            resp = await self._client.post(
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=120.0,
            )
        except httpx.TimeoutException:
            raise ProviderError(
                error_type="timeout",
                message=f"Ollama request timed out for model {self._model_id}",
                is_retryable=True,
                provider_id="ollama",
                model_id=self._model_id,
            )
        except httpx.ConnectError:
            raise ProviderError(
                error_type="model_unavailable",
                message=f"Cannot connect to Ollama at {self._base_url}. Is Ollama running?",
                is_retryable=False,
                provider_id="ollama",
                model_id=self._model_id,
            )

        if resp.status_code != 200:
            raise ProviderError(
                error_type="unknown",
                message=f"Ollama returned status {resp.status_code}: {resp.text[:200]}",
                is_retryable=resp.status_code >= 500,
                provider_id="ollama",
                model_id=self._model_id,
            )

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        usage = data.get("eval_count", 0)

        # Attempt to parse structured output if requested
        structured = None
        if request.structured_output_schema and content:
            try:
                structured = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("Ollama returned non-JSON despite format=json request")

        return ProviderResponse(
            provider_id="ollama",
            model_id=self._model_id,
            content=content,
            structured_output=structured,
            finish_reason="stop" if data.get("done") else "length",
            tokens_input=data.get("prompt_eval_count"),
            tokens_output=data.get("eval_count"),
            cost_estimate_usd=0.0,  # Local = free
            raw_response=data,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        resolved_model = await self._resolve_model_id()
        payload = self._build_payload(request, stream=True, resolved_model=resolved_model)
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=120.0,
            ) as resp:
                if resp.status_code != 200:
                    raise ProviderError(
                        error_type="unknown",
                        message=f"Ollama stream returned {resp.status_code}",
                        is_retryable=resp.status_code >= 500,
                        provider_id="ollama",
                        model_id=self._model_id,
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
        except httpx.ConnectError:
            raise ProviderError(
                error_type="model_unavailable",
                message=f"Cannot connect to Ollama at {self._base_url}",
                is_retryable=False,
                provider_id="ollama",
                model_id=self._model_id,
            )

    async def close(self) -> None:
        await self._client.aclose()
