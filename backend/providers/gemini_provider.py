"""
Google Gemini Provider
Implements BaseProvider for Google's Gemini API (via google-generativeai SDK).
Free tier available at https://aistudio.google.com/app/apikey
"""

import json
import logging
from typing import AsyncIterator, Optional

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

# Gemini model capability definitions (from official docs).
_GEMINI_MODELS: dict[str, dict] = {
    "gemini-3.8-flash": {
        "display_name": "Gemini 3.8 Flash",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_window_tokens": 1_000_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "gemini-1.5-flash": {
        "display_name": "Gemini 1.5 Flash (Aliased to 3.8)",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_window_tokens": 1_000_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "gemini-2.5-flash": {
        "display_name": "Gemini 2.5 Flash (Aliased to 3.8)",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "context_window_tokens": 1_000_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
    "gemini-1.5-pro": {
        "display_name": "Gemini 1.5 Pro (Aliased to 3.8)",
        "supported_task_types": ["code", "research", "write", "analyze", "plan", "general"],
        "input_modalities": ["text", "image", "audio", "video"],
        "output_modalities": ["text"],
        "context_window_tokens": 2_000_000,
        "max_output_tokens": 8192,
        "supports_structured_output": True,
        "supports_tool_calling": True,
        "supports_streaming": True,
    },
}

_MODEL_ALIASES = {
    "gemini-1.5-flash": "gemini-3.8-flash",
    "gemini-2.5-flash": "gemini-3.8-flash",
    "gemini-1.5-pro": "gemini-3.8-flash",
}


class GeminiProvider(BaseProvider):
    """
    Provider for Google Gemini API.
    API key must be set via GEMINI_API_KEY environment variable.
    Free tier: https://ai.google.dev/pricing
    """

    def __init__(self, model_id: Optional[str] = None):
        raw_id = model_id or settings.gemini_default_model
        self._raw_model_id = raw_id
        self._model_id = _MODEL_ALIASES.get(raw_id, raw_id)
        self._api_key = settings.gemini_api_key
        self._client = None  # Lazy init after import

    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
                if not self._api_key:
                    raise ProviderError(
                        error_type="auth",
                        message="GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/app/apikey",
                        is_retryable=False,
                        provider_id="gemini",
                        model_id=self._raw_model_id,
                    )
                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(self._model_id)
            except ImportError:
                raise ProviderError(
                    error_type="unknown",
                    message="google-generativeai package not installed. Run: pip install google-generativeai",
                    is_retryable=False,
                    provider_id="gemini",
                    model_id=self._raw_model_id,
                )
        return self._client

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def model_id(self) -> str:
        return self._raw_model_id

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and "PASTE" not in self._api_key)

    def get_capability(self) -> ProviderCapability:
        cap = _GEMINI_MODELS.get(self._raw_model_id) or _GEMINI_MODELS.get(self._model_id, {
            "display_name": f"Gemini / {self._raw_model_id}",
            "supported_task_types": ["general"],
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "context_window_tokens": 1_000_000,
            "max_output_tokens": 8192,
            "supports_structured_output": False,
            "supports_tool_calling": False,
            "supports_streaming": True,
        })
        return ProviderCapability(
            provider_id="gemini",
            model_id=self._raw_model_id,
            display_name=cap["display_name"],
            supported_task_types=cap["supported_task_types"],
            input_modalities=cap["input_modalities"],
            output_modalities=cap["output_modalities"],
            context_window_tokens=cap["context_window_tokens"],
            max_output_tokens=cap["max_output_tokens"],
            supports_structured_output=cap["supports_structured_output"],
            supports_tool_calling=cap["supports_tool_calling"],
            supports_streaming=cap["supports_streaming"],
            requires_api_key=True,
            api_key_env_var="GEMINI_API_KEY",
            base_url=None,
            is_local=False,
            is_configured=self.is_configured,
            is_enabled=settings.enable_gemini,
            capability_source="official_docs",
        )

    async def health_check(self) -> bool:
        """Check Gemini API is reachable and key is valid."""
        if not self._api_key:
            return False
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            # List models is a lightweight call to verify the key
            list(genai.list_models())
            return True
        except Exception as e:
            logger.debug("Gemini health check failed: %s", e)
            return False

    def _build_prompt(self, request: ProviderRequest) -> str:
        """Combine system prompt, context, and user message into a single prompt."""
        parts = []
        if request.system_prompt:
            parts.append(f"## Instructions\n{request.system_prompt}")
        if request.context:
            ctx_json = json.dumps(request.context, indent=2)
            parts.append(f"## Context\n```json\n{ctx_json}\n```")
        parts.append(f"## Task\n{request.user_message}")
        if request.structured_output_schema:
            schema_json = json.dumps(request.structured_output_schema, indent=2)
            parts.append(
                f"## Output Format\nRespond ONLY with valid JSON matching this schema:\n```json\n{schema_json}\n```"
            )
        return "\n\n".join(parts)

    def _map_error(self, e: Exception) -> ProviderError:
        """Map Gemini SDK exceptions to ProviderError."""
        msg = str(e).lower()
        if "api_key" in msg or "permission" in msg or "401" in msg or "403" in msg:
            return ProviderError(
                error_type="auth",
                message=f"Gemini authentication failed: {e}",
                is_retryable=False,
                provider_id="gemini",
                model_id=self._raw_model_id,
            )
        if "not found" in msg or "404" in msg:
            return ProviderError(
                error_type="unknown",
                message=f"Gemini model not found: {e}",
                is_retryable=False,
                provider_id="gemini",
                model_id=self._raw_model_id,
            )
        if "quota" in msg or "rate limit" in msg or "rate_limit" in msg or "resource_exhausted" in msg or "429" in msg:
            return ProviderError(
                error_type="rate_limit",
                message=f"Gemini rate limit hit: {e}",
                is_retryable=True,
                retry_after_seconds=60,
                provider_id="gemini",
                model_id=self._raw_model_id,
            )
        if "timeout" in msg:
            return ProviderError(
                error_type="timeout",
                message=f"Gemini request timed out: {e}",
                is_retryable=True,
                provider_id="gemini",
                model_id=self._raw_model_id,
            )
        if "safety" in msg or "blocked" in msg:
            return ProviderError(
                error_type="content_filter",
                message=f"Gemini content filter triggered: {e}",
                is_retryable=False,
                provider_id="gemini",
                model_id=self._raw_model_id,
            )
        return ProviderError(
            error_type="unknown",
            message=f"Gemini error: {e}",
            is_retryable=True,
            provider_id="gemini",
            model_id=self._raw_model_id,
        )

    async def execute(self, request: ProviderRequest) -> ProviderResponse:
        """Execute synchronously via async wrapper."""
        import asyncio

        client = self._get_client()
        prompt = self._build_prompt(request)

        try:
            # google-generativeai SDK is sync; run in thread pool
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.generate_content(
                    prompt,
                    generation_config={
                        "max_output_tokens": request.max_tokens,
                        "temperature": request.temperature,
                    },
                ),
            )
        except Exception as e:
            raise self._map_error(e)

        try:
            content = response.text
        except (ValueError, AttributeError):
            content = ""
            if hasattr(response, "candidates") and response.candidates:
                cand = response.candidates[0]
                if hasattr(cand, "content") and cand.content and cand.content.parts:
                    content = "".join(p.text for p in cand.content.parts if hasattr(p, "text"))

        # Attempt structured output parsing
        structured = None
        if request.structured_output_schema and content:
            # Strip markdown code fences if present
            clean = content.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
            try:
                structured = json.loads(clean)
            except json.JSONDecodeError:
                logger.warning("Gemini response is not valid JSON despite schema request")

        usage = getattr(response, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", None) if usage else None
        tokens_out = getattr(usage, "candidates_token_count", None) if usage else None

        return ProviderResponse(
            provider_id="gemini",
            model_id=self._model_id,
            content=content,
            structured_output=structured,
            finish_reason="stop",
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            cost_estimate_usd=None,  # Calculated externally based on token counts
            raw_response=response,
        )

    async def stream(self, request: ProviderRequest) -> AsyncIterator[str]:
        """Stream response tokens."""
        import asyncio

        client = self._get_client()
        prompt = self._build_prompt(request)

        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.generate_content(prompt, stream=True),
            )
            for chunk in response:
                try:
                    text = chunk.text
                except (ValueError, AttributeError):
                    text = ""
                    if hasattr(chunk, "candidates") and chunk.candidates:
                        cand = chunk.candidates[0]
                        if hasattr(cand, "content") and cand.content and cand.content.parts:
                            text = "".join(p.text for p in cand.content.parts if hasattr(p, "text"))
                if text:
                    yield text
        except Exception as e:
            raise self._map_error(e)
