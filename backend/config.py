"""
SYNQ Backend Configuration
All settings are loaded from environment variables (via .env file in development).
Never hardcode secrets here.
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# Explicitly load .env with override=True so local keys take precedence over stale OS env vars
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "SYNQ"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./synq.db"

    # ── FalkorDB ──────────────────────────────────────────────────────────────
    falkordb_enabled: bool = True
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_password: Optional[str] = None
    falkordb_allow_in_memory_fallback: bool = False

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2"
    ollama_models: str = "llama3.2"  # Comma-separated

    @property
    def ollama_model_list(self) -> List[str]:
        return [m.strip() for m in self.ollama_models.split(",") if m.strip()]

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: Optional[str] = None
    gemini_default_model: str = "gemini-3.8-flash"

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = None

    # ── Mistral AI ────────────────────────────────────────────────────────────
    mistral_api_key: Optional[str] = None

    # ── Hugging Face ──────────────────────────────────────────────────────────
    hf_token: Optional[str] = None

    # ── Tavily Web Search ─────────────────────────────────────────────────────
    tavily_api_key: Optional[str] = None

    # ── AWS Bedrock ──────────────────────────────────────────────────────────
    aws_bedrock_enabled: bool = False
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_default_region: str = "us-east-1"

    # ── CORS ─────────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ── Artifact Storage ─────────────────────────────────────────────────────
    artifact_storage: str = "local"
    artifact_local_path: str = "./artifacts"

    # ── Feature Flags ────────────────────────────────────────────────────────
    enable_ollama: bool = True
    enable_gemini: bool = True
    enable_aws_bedrock: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def bedrock_configured(self) -> bool:
        return (
            self.aws_bedrock_enabled
            and bool(self.aws_access_key_id)
            and bool(self.aws_secret_access_key)
        )


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Use this everywhere instead of instantiating Settings directly.
    """
    return Settings()
