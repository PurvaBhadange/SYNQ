"""
Hugging Face Provider
Implements BaseProvider for Hugging Face Serverless Inference API.
Supports Mistral (e.g. mistralai/Mistral-7B-Instruct-v0.3) using HF_TOKEN.
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

_HF_MODELS: dict[str, dict] = {
    "mistralai/Mistral-7B-Instruct-v0.3": {
        "display_name": "Hugging Face / Mistral 7B Instruct",
        "supported_task_types": ["code", "research", "write", "analyze", "general"],
        "context_window_tokens": 32_768,
        "max_output_tokens": 4096,
        "supports_structured_output": False,
        "supports_tool_calling": False,
        "supports_streaming": True,
    },
}


class HuggingFaceProvider(BaseProvider):
    """
    Provider for Hugging Face Serverless Inference API.
    """

    def __init__(self, model_id: str = "mistralai/Mistral-7B-Instruct-v0.3", token: Optional[str] = None):
        self._model_id = model_id
        self._token = token or os.getenv("HF_TOKEN", "")
        self._base_url = "https://api-inference.huggingface.co/models"

    @property
    def provider_id(self) -> str:
        return "huggingface"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def is_configured(self) -> bool:
        return bool(self._token and "PASTE" not in self._token)

    def get_capability(self) -> ProviderCapability:
        spec = _HF_MODELS.get(self._model_id, {
            "display_name": f"Hugging Face / {self._model_id}",
            "supported_task_types": ["code", "analyze", "write", "general"],
            "context_window_tokens": 16_384,
            "max_output_tokens": 2048,
            "supports_structured_output": False,
            "supports_tool_calling": False,
            "supports_streaming": True,
        })
        return ProviderCapability(
            provider_id="huggingface",
            model_id=self._model_id,
            display_name=spec["display_name"],
            supported_task_types=spec["supported_task_types"],
            context_window_tokens=spec["context_window_tokens"],
            max_output_tokens=spec["max_output_tokens"],
            supports_structured_output=spec["supports_structured_output"],
            supports_tool_calling=spec["supports_tool_calling"],
            supports_streaming=spec["supports_streaming"],
            requires_api_key=True,
            api_key_env_var="HF_TOKEN",
            base_url=f"{self._base_url}/{self._model_id}",
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
                    "https://huggingface.co/api/whoami",
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                return res.status_code == 200
        except Exception as exc:
            logger.debug("Hugging Face health check failed: %s", exc)
            return False

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        if not self.is_configured:
            raise ProviderError(
                error_type="auth",
                message="Hugging Face token not set in HF_TOKEN.",
                is_retryable=False,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )

        prompt = f"<s>[INST] <<SYS>>\n{request.system_prompt}\n<</SYS>>\n\n{request.user_message} [/INST]"
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": min(request.max_tokens, 4096),
                "temperature": request.temperature,
                "return_full_text": False,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url}/{self._model_id}",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json=payload,
                )
                if resp.status_code != 200:
                    raise ProviderError(
                        error_type="unknown",
                        message=f"Hugging Face error ({resp.status_code}): {resp.text}",
                        is_retryable=resp.status_code in (429, 500, 502, 503),
                        provider_id=self.provider_id,
                        model_id=self.model_id,
                    )
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    content = data[0].get("generated_text", "")
                elif isinstance(data, dict):
                    content = data.get("generated_text", "")
                else:
                    content = str(data)

                return ProviderResponse(
                    provider_id=self.provider_id,
                    model_id=self.model_id,
                    content=content,
                    raw_response=data,
                )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                error_type="unknown",
                message=f"Hugging Face network error: {exc}",
                is_retryable=True,
                provider_id=self.provider_id,
                model_id=self.model_id,
            )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        # Serverless HF handles non-streaming smoothly; yield the completed generation
        resp = await self.execute(request)
        # Yield in chunks for smooth UI token animation
        chunk_size = 16
        for i in range(0, len(resp.content), chunk_size):
            yield resp.content[i : i + chunk_size]
