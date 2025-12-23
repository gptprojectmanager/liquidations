"""
Main FastAPI application for Margin Tier API.

Provides REST endpoints for:
- Margin tier calculations
- Liquidation price calculations
- Tier information and comparison
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def get_cors_origins() -> list[str]:
    """Get CORS allowed origins from environment.

    In production, set CORS_ALLOWED_ORIGINS to comma-separated list of origins.
    Example: CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

    Returns:
        List of allowed origins. Defaults to ["*"] for development.
    """
    origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if origins_env:
        return [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    # Development default - allow all origins
    return ["*"]


# Import routers
from src.api.endpoints.clustering import router as clustering_router
from src.api.endpoints.margin import router as margin_router
from src.api.endpoints.rollback import router as rollback_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Margin Tier API...")

    yield

    # Shutdown
    logger.info("Shutting down Margin Tier API...")


# Initialize FastAPI app (T044: Updated docs with clustering endpoints)
app = FastAPI(
    title="Liquidation Heatmap API",
    description="""
    Calculate margin requirements, liquidation prices, and cluster liquidation zones.

    **Key Features:**
    - Margin tier calculations with Binance rules
    - DBSCAN clustering for liquidation zone identification
    - Real-time cluster updates with caching
    - Auto-tuning for optimal clustering parameters
    """,
    version="1.1.0",  # Incremented for clustering feature
    lifespan=lifespan,
)

# CORS middleware (configurable via CORS_ALLOWED_ORIGINS env var)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(margin_router, prefix="/api")
app.include_router(rollback_router, prefix="/api")
app.include_router(clustering_router, prefix="/api")


@app.get("/health")
async def root_health():
    """Root health check."""
    return {"status": "ok", "service": "margin-tier-api", "version": "1.0.0"}
