"""Background job processing with ARQ (async Redis queue).

ARQ is an async-native task queue built on Redis, perfect for FastAPI applications.
It's simpler and more lightweight than Celery, with excellent async/await support.

Features:
- Async/await native
- Job retries with exponential backoff
- Scheduled/cron jobs
- Job result storage
- Worker pooling

Alternative: For heavier workloads or complex workflows, see Celery patterns at the
bottom of this file.

Setup:
    1. Install ARQ:
       uv add arq redis

    2. Start Redis:
       docker-compose up -d redis

    3. Configure in .env:
       REDIS_URL=redis://localhost:6379/0

    4. Run worker:
       arq audio_processor.jobs.worker.WorkerSettings
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

if TYPE_CHECKING:
    from arq.connections import ArqRedis

logger = logging.getLogger(__name__)


# =============================================================================
# Task Functions
# =============================================================================


async def example_background_task(
    ctx: dict[str, Any], user_id: str, _data: dict
) -> dict:
    """Example background task.

    Args:
        ctx: ARQ context (contains redis connection, job_id, etc.)
        user_id: User identifier
        data: Task data

    Returns:
        Result dictionary
    """
    logger.info("background_task_started", user_id=user_id, job_id=ctx.get("job_id"))

    # Simulate some work
    await asyncio.sleep(2)

    # Access Redis for storing results
    redis: ArqRedis = ctx["redis"]
    await redis.set(f"task_result:{user_id}", "completed", expire=3600)

    logger.info("background_task_completed", user_id=user_id)

    return {
        "status": "success",
        "user_id": user_id,
        "processed_at": datetime.now(UTC).isoformat(),
    }


async def send_email_task(
    _ctx: dict[str, Any],
    recipient: str,
    subject: str,
    _body: str,
) -> dict:
    """Send email asynchronously.

    Args:
        ctx: ARQ context
        recipient: Email recipient
        subject: Email subject
        body: Email body

    Returns:
        Send status
    """
    logger.info("sending_email", recipient=recipient, subject=subject)

    # TODO: Integrate with your email provider
    # Example with SendGrid, AWS SES, etc.

    await asyncio.sleep(1)  # Simulate email sending

    return {
        "status": "sent",
        "recipient": recipient,
        "sent_at": datetime.now(UTC).isoformat(),
    }


async def process_file_upload(
    _ctx: dict[str, Any],
    file_id: str,
    file_path: str,
) -> dict:
    """Process uploaded file in background.

    Args:
        ctx: ARQ context
        file_id: File identifier
        file_path: Path to uploaded file

    Returns:
        Processing result
    """
    logger.info("processing_file", file_id=file_id, path=file_path)

    try:
        # Example: Read and process file

        await asyncio.sleep(3)  # Simulate processing

        return {
            "status": "completed",
            "file_id": file_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "records_processed": 1000,
        }

    except Exception:
        logger.exception("file_processing_failed", file_id=file_id)
        raise


async def cleanup_old_data(_ctx: dict[str, Any]) -> int:
    """Scheduled task to clean up old data.

    This runs daily via cron schedule defined in WorkerSettings.

    Args:
        ctx: ARQ context

    Returns:
        Number of records cleaned
    """
    logger.info("cleanup_task_started")

    # Example: Delete old records

    deleted_count = 0  # Placeholder
    logger.info("cleanup_task_completed", deleted=deleted_count)

    return deleted_count


# =============================================================================
# Startup and Shutdown Hooks
# =============================================================================


async def startup(_ctx: dict[str, Any]) -> None:
    """Worker startup hook.

    Runs once when the worker starts.
    Use for initializing connections, caches, etc.

    Args:
        ctx: ARQ context
    """
    logger.info("arq_worker_starting")

    # Example: Initialize database connection or load configuration


async def shutdown(_ctx: dict[str, Any]) -> None:
    """Worker shutdown hook.

    Runs once when the worker shuts down gracefully.
    Use for closing connections, cleaning up resources.

    Args:
        ctx: ARQ context
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
    functions: ClassVar = [
        example_background_task,
        send_email_task,
        process_file_upload,
    ]

    # Scheduled tasks (cron)
    cron_jobs: ClassVar = [
        cron(cleanup_old_data, hour=2, minute=0),  # Run daily at 2 AM
    ]

    # Redis connection
    redis_settings = RedisSettings.from_dsn(
        "redis://localhost:6379/0"  # Override with REDIS_URL env var
    )

    # Worker configuration
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = 300  # Job timeout in seconds (5 minutes)
    keep_result = 3600  # Keep job results for 1 hour

    # Retry configuration
    max_tries = 3  # Maximum retry attempts
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
    *args: Any,
    **kwargs: Any,
) -> str:
    """Enqueue a background task.

    Args:
        redis: ARQ Redis connection
        task_name: Name of the task function
        *args: Task arguments
        **kwargs: Task keyword arguments

    Returns:
        Job ID

    Example:
        >>> from arq import create_pool
        >>> redis = await create_pool(RedisSettings())
        >>> job_id = await enqueue_task(
        ...     redis, "example_background_task", "user_123", {"action": "export"}
        ... )
    """
    job = await redis.enqueue_job(task_name, *args, **kwargs)
    logger.info("task_enqueued", task=task_name, job_id=job.job_id)
    return job.job_id


# =============================================================================
# FastAPI Integration Example
# =============================================================================

"""
# In your FastAPI app:

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Depends

app = FastAPI()

# Create Redis pool on startup
@app.on_event("startup")
async def startup_event():
    app.state.arq_pool = await create_pool(RedisSettings())

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.arq_pool.close()

# Dependency to get ARQ pool
async def get_arq_pool() -> ArqRedis:
    return app.state.arq_pool

# Enqueue task from endpoint
@app.post("/api/process")
async def process_data(
    data: dict,
    arq: ArqRedis = Depends(get_arq_pool)
):
    job = await arq.enqueue_job(
        "example_background_task",
        user_id="user_123",
        data=data,
    )

    return {
        "job_id": job.job_id,
        "status": "queued"
    }

# Check job status
@app.get("/api/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    arq: ArqRedis = Depends(get_arq_pool)
):
    job = Job(job_id, redis=arq)
    status = await job.status()
    result = await job.result()

    return {
        "job_id": job_id,
        "status": status,
        "result": result
    }
"""


# =============================================================================
# Celery Alternative (for more complex use cases)
# =============================================================================

"""
# For heavier workloads, complex workflows, or when you need:
# - Task chaining and groups
# - Periodic task scheduling with crontab
# - Multiple queue priorities
# - Extensive monitoring tools
# - Broader ecosystem support

# Use Celery instead of ARQ:

from celery import Celery
from celery.schedules import crontab

# Initialize Celery
celery_app = Celery(
    "audio_processor",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)

# Define tasks
@celery_app.task(bind=True, max_retries=3)
def example_celery_task(self, user_id: str, data: dict):
    try:
        # Process task
        result = process_data(user_id, data)
        return result
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

# Periodic tasks
celery_app.conf.beat_schedule = {
    'cleanup-every-day': {
        'task': 'cleanup_old_data',
        'schedule': crontab(hour=2, minute=0),
    },
}

# Run worker:
# celery -A audio_processor.jobs.celery_worker worker --loglevel=info

# Run beat scheduler:
# celery -A audio_processor.jobs.celery_worker beat --loglevel=info
"""
