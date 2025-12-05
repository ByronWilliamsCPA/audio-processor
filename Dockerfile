# Multi-stage Dockerfile for Audio Processor
# Optimized for production with security best practices and minimal image size

# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
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
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12-slim

# Metadata labels (OCI standard)
LABEL org.opencontainers.image.title="Audio Processor"
LABEL org.opencontainers.image.description="Audio file conversion and processing for RAG content pipelines"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.authors="Byron Williams <byron@williamshome.family>"
LABEL org.opencontainers.image.url="https://github.com/ByronWilliamsCPA/audio-processor"
LABEL org.opencontainers.image.source="https://github.com/ByronWilliamsCPA/audio-processor"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

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
    PYTHONPATH=/app/src

# Switch to non-root user
USER appuser

# Expose port (default for FastAPI/web apps)
# EXPOSE 8000  # Uncomment if running a web server
# Default command - run CLI (override as needed)
ENTRYPOINT ["audio_processor"]
CMD ["--help"]
# =============================================================================
# Build Arguments (optional, for build-time configuration)
# =============================================================================
# Example:
# ARG BUILD_ENV=production
# ENV ENVIRONMENT=${BUILD_ENV}

# =============================================================================
# Multi-architecture support
# =============================================================================
# Build for multiple platforms:
# docker buildx build --platform linux/amd64,linux/arm64 -t myimage:latest .
