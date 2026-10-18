"""
Provider Registry Initialization
Called during application startup to register all configured providers.
"""

import logging

from config import get_settings
from core.capability_registry import registry
from providers.ollama import OllamaProvider
from providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)
settings = get_settings()


async def initialize_providers() -> None:
    """
    Register all configured providers with the CapabilityRegistry.
    Called once at application startup.
    """
    logger.info("Initializing provider registry...")

    # ── Ollama (Local) ────────────────────────────────────────────────────────
    if settings.enable_ollama:
        models_to_register = list(settings.ollama_model_list)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                if r.status_code == 200:
                    for m in r.json().get("models", []):
                        name = m.get("name")
                        if name and name not in models_to_register:
                            models_to_register.append(name)
        except Exception as exc:
            logger.debug("Could not auto-discover Ollama models: %s", exc)

        for model_id in models_to_register:
            provider = OllamaProvider(model_id=model_id)
            is_healthy = await provider.health_check()
            if not is_healthy:
                logger.warning(
                    "Ollama provider '%s' registered but marked unavailable at %s.",
                    model_id,
                    settings.ollama_base_url,
                )
            registry.register_provider(provider)
    else:
        logger.info("Ollama disabled (ENABLE_OLLAMA=false)")

    # ── Google Gemini (Cloud) ─────────────────────────────────────────────────
    if settings.enable_gemini:
        gemini = GeminiProvider(model_id=settings.gemini_default_model)
        if not settings.gemini_configured:
            logger.warning(
                "Gemini API key not set. Provider registered but will not route tasks. "
                "Set GEMINI_API_KEY in .env to enable cloud inference."
            )
        else:
            logger.info("Gemini provider configured with model: %s", settings.gemini_default_model)
        registry.register_provider(gemini)
        registry.register_provider(GeminiProvider(model_id="gemini-1.5-flash"))
    else:
        logger.info("Gemini disabled (ENABLE_GEMINI=false)")

    # ── Groq (Cloud - LPU Inference) ──────────────────────────────────────────
    from providers.groq_provider import GroqProvider, _GROQ_MODELS
    for groq_model in _GROQ_MODELS:
        groq_p = GroqProvider(model_id=groq_model)
        registry.register_provider(groq_p)
        if groq_p.is_configured:
            logger.info("Groq provider configured with model: %s", groq_model)

    # ── Hugging Face (Mistral / Open Source Cloud) ────────────────────────────
    from providers.huggingface_provider import HuggingFaceProvider, _HF_MODELS
    for hf_model in _HF_MODELS:
        hf_p = HuggingFaceProvider(model_id=hf_model)
        registry.register_provider(hf_p)
        if hf_p.is_configured:
            logger.info("Hugging Face provider configured with model: %s", hf_model)

    # ── Mistral AI (Official API) ─────────────────────────────────────────────
    from providers.mistral_provider import MistralProvider, _MISTRAL_MODELS
    for mistral_model in _MISTRAL_MODELS:
        mistral_p = MistralProvider(model_id=mistral_model)
        registry.register_provider(mistral_p)
        if mistral_p.is_configured:
            logger.info("Mistral AI provider configured with model: %s", mistral_model)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = registry.summary()
    logger.info(
        "Provider registry ready: %d registered, %d configured (%d local, %d cloud)",
        summary["total_registered"],
        summary["configured"],
        summary["local"],
        summary["cloud"],
    )
