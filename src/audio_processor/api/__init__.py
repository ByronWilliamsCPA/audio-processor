"""Audio Processor FastAPI Application.

Provides REST API endpoints for audio file processing, transcription,
and job management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from audio_processor.api.routes import router as audio_router
from audio_processor.core.config import settings
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import Request

logger = get_logger(__name__)


# basedpyright 1.39 typeshed wrongly flags stdlib asynccontextmanager as deprecated
@asynccontextmanager  # pyright: ignore[reportDeprecated]
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application-scoped resources.

    When the Redis job-store backend is configured, opens an ARQ pool and
    attaches a shared :class:`RedisJobStore` to ``app.state`` so the API and the
    worker observe the same job state, then enqueues submitted jobs through it.
    For the default in-memory backend this is a no-op (no Redis connection).

    Args:
        app (FastAPI): The FastAPI application.

    Yields:
        None: Control to the running application.
    """
    arq_pool = None
    if settings.job_store_backend == "redis":
        from arq import create_pool  # noqa: PLC0415
        from arq.connections import RedisSettings  # noqa: PLC0415

        from audio_processor.core.job_store import RedisJobStore  # noqa: PLC0415

        arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.arq_pool = arq_pool
        app.state.job_store = RedisJobStore(arq_pool)
        logger.info("redis_job_store_initialized")
    try:
        yield
    finally:
        if arq_pool is not None:
            await arq_pool.close()
            logger.info("redis_job_store_closed")


# Application metadata
APP_TITLE = "Audio Processor API"
APP_DESCRIPTION = """
Audio file conversion and processing for RAG content pipelines.

## Features

- **Audio Processing**: Submit audio/video files for transcription
- **Speaker Diarization**: Identify and label different speakers
- **Summarization**: Generate AI-powered summaries
- **Quality Assessment**: Analyze audio quality metrics

## Workflow

1. **Submit**: POST /api/v1/process with audio file
2. **Track**: GET /api/v1/status/{job_id} to check progress
3. **Retrieve**: GET /api/v1/results/{job_id} when complete
"""
try:
    _app_version = _pkg_version("audio-processor")
except PackageNotFoundError:
    _app_version = "unknown"
APP_VERSION: str = _app_version

# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Audio Processing",
            "description": "Audio file submission, status tracking, and results retrieval",
        },
        {
            "name": "Health",
            "description": "Service health monitoring",
        },
    ],
)

# Include API routes
app.include_router(audio_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for container orchestration.

    Returns:
        dict[str, str]: Dictionary with status indicating service health.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns:
        dict[str, str]: Dictionary with API title and version.
    """
    return {
        "title": APP_TITLE,
        "version": APP_VERSION,
        "docs": "/docs",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors.

    Logs the exception with full context and returns a safe, generic error message
    to avoid exposing internal details in production.

    Args:
        request (Request): The incoming request.
        exc (Exception): The exception that was raised.

    Returns:
        JSONResponse: JSON response with generic error message.
    """
    # Log the exception with full context for debugging and monitoring.
    # This handler runs outside a lexical `except` block (FastAPI calls it
    # with the exception instance rather than re-raising into one), so
    # logger.exception()'s implicit sys.exc_info() lookup is not reliable
    # here; pass the exception explicitly via exc_info instead.
    logger.error(
        "unhandled_exception",
        exc_info=exc,
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        path=str(request.url.path),
        method=request.method,
    )

    # Never expose internal exception details in the response
    # (even in DEBUG mode - use logs/Sentry for debugging)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please contact support.",
        },
    )
