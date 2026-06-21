import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import auth as auth_router
from app.api.routers import documents as documents_router
from app.config import settings
from app.core.qdrant import close_qdrant_client, ensure_collection, get_qdrant_client
from app.core.redis import close_redis_pool, get_redis_pool

# Setup logging configuration
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# FastAPI Lifespan Manager
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup phase
    logger.info("%s v%s starting up", settings.app_title, settings.app_version)
    get_redis_pool()
    get_qdrant_client()
    await ensure_collection()
    logger.info("All infrastructure clients initialized")
    yield
    # Shutdown phase
    await close_qdrant_client()
    await close_redis_pool()
    logger.info("%s shut down gracefully", settings.app_title)


# Initialize FastAPI Application
app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "Enterprise Cloud AI Agent & RAG System.\n\n"
        "Corporate HR Assistant powered by LangGraph, Qdrant, and OpenAI."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    response_description="Service health status and version metadata",
)
async def health_check() -> dict[str, str]:
    logger.debug("Health check endpoint called")
    return {
        "status": "ok",
        "service": settings.app_title,
        "version": settings.app_version,
    }


API_V1_PREFIX = "/api/v1"

app.include_router(auth_router.router, prefix=API_V1_PREFIX)
app.include_router(documents_router.router, prefix=API_V1_PREFIX)
