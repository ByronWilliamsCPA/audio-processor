"""Background job processing with ARQ (async Redis queue).

ARQ is an async-native task queue built on Redis, perfect for FastAPI applications.
It's simpler and more lightweight than Celery, with excellent async/await support.

Features:
- Async/await native
- Job retries with exponential backoff
- Job result storage
- Worker pooling

Setup:
    1. Install ARQ:
       uv sync --extra jobs

    2. Start Redis:
       docker-compose up -d redis

    3. Configure in .env:
       REDIS_URL=redis://localhost:6379/0

    4. Run worker:
       arq audio_processor.jobs.worker.WorkerSettings
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from arq.connections import RedisSettings

from audio_processor.core.config import settings
from audio_processor.jobs.audio_tasks import process_audio_job

if TYPE_CHECKING:
    from arq.connections import ArqRedis

    # ARQ context contains the redis connection, job_id, etc.
    JobContext = dict[str, object]

logger = logging.getLogger(__name__)


# =============================================================================
# Startup and Shutdown Hooks
# =============================================================================


async def startup(ctx: JobContext) -> None:  # noqa: ARG001
    """Worker startup hook.

    Runs once when the worker starts.
    Use for initializing connections, caches, etc.

    Args:
        ctx (JobContext): ARQ context (required by ARQ but unused in this function)
    """
    logger.info("arq_worker_starting")

    # Example: Initialize database connection or load configuration


async def shutdown(ctx: JobContext) -> None:  # noqa: ARG001
    """Worker shutdown hook.

    Runs once when the worker shuts down gracefully.
    Use for closing connections, cleaning up resources.

    Args:
        ctx (JobContext): ARQ context (required by ARQ but unused in this function)
    """
    logger.info("arq_worker_shutting_down")

    # Example: Close database connection if needed


# =============================================================================
# Worker Configuration
# =============================================================================


class WorkerSettings:
    """ARQ worker configuration.

    This class configures the ARQ worker process.
    """

    # Task functions to register
    # ARQ worker expects a list of callable functions - type varies
    functions: ClassVar[list[object]] = [  # pyright: ignore[reportUnknownVariableType]
        process_audio_job,
    ]

    # Redis connection - use settings
    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Worker configuration
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = settings.job_timeout_seconds  # Job timeout from settings
    keep_result = settings.job_result_ttl_seconds  # Result TTL from settings

    # Retry configuration
    max_tries = settings.job_max_retries  # Max retries from settings
    retry_jobs = True  # Enable automatic retries

    # Lifecycle hooks
    on_startup = startup
    on_shutdown = shutdown

    # Health check
    health_check_interval = 60  # Check worker health every 60 seconds


# =============================================================================
# Enqueue Tasks from FastAPI
# =============================================================================


async def enqueue_task(
    redis: ArqRedis,
    task_name: str,
    *args: Any,  # ARQ's enqueue_job has complex signature - Any needed for **kwargs spread  # pyright: ignore[reportExplicitAny, reportAny]
    **kwargs: Any,  # pyright: ignore[reportExplicitAny, reportAny]
) -> str:
    """Enqueue a background task.

    Args:
        redis (ArqRedis): ARQ Redis connection
        task_name (str): Name of the task function
        *args (Any): Task arguments
        **kwargs (Any): Task keyword arguments

    Returns:
        str: Job ID string.

    Raises:
        RuntimeError: If task enqueueing fails.

    Example:
        >>> from arq import create_pool
        >>> redis = await create_pool(RedisSettings())
        >>> job_id = await enqueue_task(
        ...     redis, "example_background_task", "user_123", {"action": "export"}
        ... )
    """
    # ARQ's enqueue_job accepts variadic args - type checking limitation
    job = await redis.enqueue_job(task_name, *args, **kwargs)  # pyright: ignore[reportAny]
    if job is None:
        msg = f"Failed to enqueue task: {task_name}"
        raise RuntimeError(msg)
    logger.info("task_enqueued", task=task_name, job_id=job.job_id)  # type: ignore[call-arg]
    return job.job_id
