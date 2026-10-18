"""
Mistral AI Provider
Implements BaseProvider for Mistral AI's official API (La Plateforme).
Uses MISTRAL_API_KEY from environment.
Get a key at https://console.mistral.ai/
"""

import json
import logging
import os
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

_MISTRAL_MODELS: dict[str, dict] = {
    "mistral-small-latest": {
        "display_name": "Mistral / Small (Reasoning & Code)",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "mistral-large-latest": {
        "display_name": "Mistral / Large (Frontier Model)",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "context_window_tokens": 128_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "codestral-latest": {
        "display_name": "Mistral / Codestral (Code Specialist)",
        "supported_task_types": ["code", "analyze", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
}

_DEFAULT_CAPABILITY = {
    "display_name": "Mistral Model",
    "supported_task_types": ["code", "analyze", "write", "general"],
    "context_window_tokens": 32_768,
    "max_output_tokens": 4096,
    "supports_structured_output": True,
    "supports_tool_calling": True,
    "supports_streaming": True,
}


class MistralProvider(BaseProvider):
    """
    Provider for official Mistral AI API.
    """

    def __init__(self, model_id: str = "mistral-small-latest", api_key: Optional[str] = None):
        self._model_id = model_id
        self._api_key = api_key or os.getenv("MISTRAL_API_KEY", "")
        self._base_url = "https://api.mistral.ai/v1"

    @property
    def provider_id(self) -> str:
        return "mistral"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and "PASTE" not in self._api_key)

    def get_capability(self) -> ProviderCapability:
        spec = _MISTRAL_MODELS.get(self._model_id, _DEFAULT_CAPABILITY)
        return ProviderCapability(
            provider_id="mistral",
            model_id=self._model_id,
            display_name=spec.get("display_name", f"Mistral / {self._model_id}"),
            supported_task_types=spec["supported_task_types"],
            context_window_tokens=spec["context_window_tokens"],
            max_output_tokens=spec["max_output_tokens"],
            supports_structured_output=spec["supports_structured_output"],
            supports_tool_calling=spec["supports_tool_calling"],
            supports_streaming=spec["supports_streaming"],
            requires_api_key=True,
            api_key_env_var="MISTRAL_API_KEY",
            base_url=self._base_url,
            is_local=False,
            is_configured=self.is_configured,
            is_enabled=True,
            capability_source="official_docs",
        )

    async def health_check(self) -> bool:
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return res.status_code == 200
        except Exception as exc:
            logger.debug("Mistral health check failed: %s", exc)
            return False

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        if not self.is_configured:
            raise ProviderError(
                error_type="auth",
                message="Mistral API key not set in MISTRAL_API_KEY.",
                is_retryable=False,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_message},
        ]
        payload = {
            "model": self._model_id,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": min(request.max_tokens, 8192),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code != 200:
                    raise ProviderError(
                        error_type="unknown",
                        message=f"Mistral error ({resp.status_code}): {resp.text}",
                        is_retryable=resp.status_code in (429, 500, 502, 503),
                        provider_id=self.provider_id,
                        model_id=self.model_id,
                    )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return ProviderResponse(
                    provider_id=self.provider_id,
                    model_id=self.model_id,
                    content=content,
                    tokens_input=usage.get("prompt_tokens"),
                    tokens_output=usage.get("completion_tokens"),
                    raw_response=data,
                )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                error_type="unknown",
                message=f"Mistral network error: {exc}",
                is_retryable=True,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        if not self.is_configured:
            raise ProviderError(
                error_type="auth",
                message="Mistral API key not set in MISTRAL_API_KEY.",
                is_retryable=False,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )

        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_message},
        ]
        payload = {
            "model": self._model_id,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": min(request.max_tokens, 8192),
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        err_text = await resp.aread()
                        raise ProviderError(
                            error_type="unknown",
                            message=f"Mistral stream failed ({resp.status_code}): {err_text.decode('utf-8', errors='ignore')}",
                            is_retryable=resp.status_code in (429, 500, 502, 503),
                            provider_id=self.provider_id,
                            model_id=self.model_id,
                        )
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                error_type="unknown",
                message=f"Mistral streaming error: {exc}",
                is_retryable=True,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )
