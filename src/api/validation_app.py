"""
FastAPI application for Validation Suite.

Simple, secure API for model validation with KISS principles.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.endpoints import dashboard, trends, validation
from src.validation.logger import logger
from src.validation.middleware import RateLimiterMiddleware, SecurityHeadersMiddleware
from src.validation.security_config import get_security_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("🚀 Starting Validation API...")
    yield
    # Shutdown
    logger.info("👋 Shutting down Validation API...")


# Create FastAPI app
app = FastAPI(
    title="Liquidation Model Validation API",
    description="REST API for liquidation model validation, trends, and monitoring",
    version="1.0.0",
    lifespan=lifespan,
    # Disable docs in production if needed
    docs_url="/docs",
    redoc_url="/redoc",
)

# Security settings
settings = get_security_settings()

# Add CORS middleware (restrictive by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    max_age=settings.cors_max_age,
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimiterMiddleware)

# Include validation routers
app.include_router(validation.router)
app.include_router(trends.router)
app.include_router(dashboard.router)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "validation-api",
        "version": "1.0.0",
        "security": {
            "rate_limiting": settings.rate_limit_enabled,
            "security_headers": settings.enable_security_headers,
            "csp": settings.enable_csp,
        },
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "Liquidation Model Validation API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
