"""FastAPI application factory for Hermesfy V5.

Usage:
    uvicorn hermesfy.api.app:create_app --factory --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from hermesfy.api.deps import get_settings
from hermesfy.api.errors import AppError, ErrorEnvelope
from hermesfy.api.routes import (
    approvals_router,
    chat_router,
    dag_router,
    health_router,
    runs_router,
    ws_router,
)
from hermesfy.api.settings import Settings
from hermesfy.storage.db import ensure_schema

logger = logging.getLogger("hermesfy.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: init DB schema on startup, cleanup on shutdown."""
    settings: Settings = get_settings()
    # Ensure DB schema exists
    await ensure_schema(settings)
    logger.info(
        "Hermesfy V5 API starting on %s:%d (data_dir=%s)",
        settings.host,
        settings.port,
        settings.data_dir,
    )
    yield
    logger.info("Hermesfy V5 API shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Hermesfy Studio V5 API",
        description="Lite DAG workflow engine API — Agentic Visual Studio",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(chat_router, prefix="/api")
    app.include_router(dag_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")
    app.include_router(approvals_router, prefix="/api")
    app.include_router(ws_router)

    # Global exception handler for AppError
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_envelope().model_dump(),
        )

    # Generic exception handler
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        envelope = ErrorEnvelope(
            error="INTERNAL_ERROR",
            message="An unexpected error occurred",
        )
        return JSONResponse(
            status_code=500,
            content=envelope.model_dump(),
        )

    return app
