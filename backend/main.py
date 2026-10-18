"""
SYNQ FastAPI Application — Main Entry Point
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.session import init_db
from providers.registry_init import initialize_providers
from api.v1.projects import router as projects_router
from api.v1.providers import router as providers_router
from api.v1.tasks import router as tasks_router
from api.v1.memory import router as memory_router
from api.v1.ws import router as ws_router
from api.v1.export import router as export_router

# ── Logging ───────────────────────────────────────────────────────────────────
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.DEBUG if get_settings().debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("synq")
settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: run setup on startup, cleanup on shutdown."""
    logger.info("========================================")
    logger.info("  SYNQ Backend starting up (%s)", settings.app_env)
    logger.info("========================================")

    # Initialize operational database
    await init_db()
    logger.info("Database initialized: %s", settings.database_url)

    # Register AI providers
    await initialize_providers()

    # FalkorDB graph memory initialization
    from memory.falkordb_client import falkor_client
    falkor_client.connect()
    if falkor_client.is_connected:
        logger.info("FalkorDB graph memory connected at %s:%s", settings.falkordb_host, settings.falkordb_port)
    elif settings.falkordb_allow_in_memory_fallback:
        logger.warning("FalkorDB not connected; explicit IN-MEMORY TEST adapter active.")
    else:
        logger.warning("FalkorDB not connected at %s:%s; graph operations paused. Operational SQLite store active.", settings.falkordb_host, settings.falkordb_port)

    logger.info("SYNQ is ready. API docs: http://localhost:8000/docs")
    yield

    logger.info("SYNQ shutting down...")
    falkor_client.close()


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SYNQ API",
    description=(
        "SYNQ — AI Agent Orchestration Platform. "
        "Multi-agent coordination with shared persistent memory."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(projects_router, prefix="/api/v1")
app.include_router(providers_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")
app.include_router(export_router, prefix="/api/v1")


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    """System health check."""
    from core.capability_registry import registry
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "env": settings.app_env,
        "providers": registry.summary(),
    }


@app.get("/", tags=["system"])
async def root():
    return {"message": "SYNQ API is running. Visit /docs for API documentation."}
