# Multi-stage Dockerfile for Audio Processor
# Optimized for production with audio processing capabilities

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages
# Including audio libraries needed to compile librosa, soundfile, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    # Audio processing build dependencies
    libsndfile1-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install UV for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies to a virtual environment
# This creates .venv/ which we'll copy to the final stage
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# =============================================================================
# Stage 2: Runtime - Production image with audio processing capabilities
# =============================================================================
FROM python:3.12-slim AS runtime

# =============================================================================
# Build Arguments
# =============================================================================
ARG BUILD_ENV=production
ENV ENVIRONMENT=${BUILD_ENV}

# Metadata labels (OCI standard)
LABEL org.opencontainers.image.title="Audio Processor"
LABEL org.opencontainers.image.description="Audio file conversion and processing for RAG content pipelines"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.authors="Byron Williams <byron@williamshome.family>"
LABEL org.opencontainers.image.url="https://github.com/ByronWilliamsCPA/audio-processor"
LABEL org.opencontainers.image.source="https://github.com/ByronWilliamsCPA/audio-processor"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime dependencies for audio processing
# NOTE: Upgrade libpng16-16t64 to fix CVE-2025-64720, CVE-2025-65018, CVE-2025-66293
# libglib2.0-0t64 CVE-2025-13601 remains unfixed in Debian (see .trivyignore)
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    # FFmpeg for audio/video extraction and conversion
    ffmpeg \
    # libsndfile for soundfile Python package
    libsndfile1 \
    # Additional audio codec support
    libavcodec-extra \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Create temp directory for audio processing
RUN mkdir -p /app/temp && chown appuser:appuser /app/temp

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    # Audio processing temp directory
    AUDIO_TEMP_DIR=/app/temp

# Expose port for FastAPI
EXPOSE 8000

# Switch to non-root user
USER appuser

# Default command - can be overridden in docker-compose
# For API server: uvicorn audio_processor.api:app --host 0.0.0.0 --port 8000
# For ARQ worker: arq audio_processor.jobs.worker.WorkerSettings
CMD ["audio_processor", "--help"]

# =============================================================================
# Multi-architecture support
# =============================================================================
# Build for multiple platforms:
# docker buildx build --platform linux/amd64,linux/arm64 -t myimage:latest .
