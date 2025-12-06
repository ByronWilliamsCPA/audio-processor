"""Audio Processor FastAPI Application.

Provides REST API endpoints for audio file processing, transcription,
and job management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from audio_processor.core.config import settings
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request

logger = get_logger(__name__)

# Application metadata
APP_TITLE = "Audio Processor API"
APP_DESCRIPTION = "Audio file conversion and processing for RAG content pipelines"
APP_VERSION = "0.1.0"

# Create FastAPI application
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint for container orchestration.

    Returns:
        Dictionary with status indicating service health.
    """
    return {"status": "healthy"}


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns:
        Dictionary with API title and version.
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
        request: The incoming request.
        exc: The exception that was raised.

    Returns:
        JSON response with generic error message.
    """
    # Log the exception with full context for debugging and monitoring
    logger.exception(
        "unhandled_exception",
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
