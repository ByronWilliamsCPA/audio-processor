"""Background job processing for Audio Processor.

This package provides background task processing using ARQ (async Redis queue).

Usage:
    # Start worker
    arq audio_processor.jobs.worker.WorkerSettings

    # Enqueue tasks from your FastAPI app
    from audio_processor.jobs.worker import enqueue_task

    job_id = await enqueue_task(
        redis,
        "process_audio_job",
        job_id="123",
        job_data={"input": {...}}
    )
"""

from __future__ import annotations

from audio_processor.jobs.audio_tasks import process_audio_job

__all__ = ["process_audio_job"]
