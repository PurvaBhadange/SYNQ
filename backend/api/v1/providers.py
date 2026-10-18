"""
Providers API endpoints.
Exposes the Capability Registry and provider health status to the frontend.
"""

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from core.capability_registry import registry

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    provider_id: str
    model_id: str
    display_name: str
    is_local: bool
    is_configured: bool
    is_enabled: bool
    supported_task_types: List[str]
    context_window_tokens: int
    supports_streaming: bool
    supports_structured_output: bool
    supports_tool_calling: bool
    capability_source: str


class RegistryStatus(BaseModel):
    total_registered: int
    configured: int
    local: int
    cloud: int
    providers: List[ProviderInfo]


@router.get("/", response_model=RegistryStatus)
async def list_providers():
    """Return all registered providers and their capabilities."""
    caps = registry.list_all_capabilities()
    providers = [
        ProviderInfo(
            provider_id=c.provider_id,
            model_id=c.model_id,
            display_name=c.display_name,
            is_local=c.is_local,
            is_configured=c.is_configured,
            is_enabled=c.is_enabled,
            supported_task_types=c.supported_task_types,
            context_window_tokens=c.context_window_tokens,
            supports_streaming=c.supports_streaming,
            supports_structured_output=c.supports_structured_output,
            supports_tool_calling=c.supports_tool_calling,
            capability_source=c.capability_source,
        )
        for c in caps
    ]
    return RegistryStatus(
        total_registered=len(caps),
        configured=sum(1 for c in caps if c.is_configured),
        local=sum(1 for c in caps if c.is_local),
        cloud=sum(1 for c in caps if not c.is_local),
        providers=providers,
    )


from urllib.parse import unquote

@router.get("/{provider_id}/{model_id:path}/health")
async def check_provider_health(provider_id: str, model_id: str):
    """Check live health of a specific provider."""
    decoded_model_id = unquote(model_id)
    provider = registry.get_provider(provider_id, decoded_model_id) or registry.get_provider(provider_id, model_id)
    if not provider:
        return {"healthy": False, "error": "Provider not registered"}
    try:
        healthy = await provider.health_check()
        return {"healthy": healthy, "provider_id": provider_id, "model_id": model_id}
    except Exception as e:
        return {"healthy": False, "error": str(e)}
