"""Tests for ARQ background job worker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_processor.jobs.audio_tasks import process_audio_job
from audio_processor.jobs.worker import (
    WorkerSettings,
    enqueue_task,
    shutdown,
    startup,
)


class TestWorkerLifecycle:
    """Tests for worker startup and shutdown hooks."""

    @pytest.mark.asyncio
    async def test_startup(self) -> None:
        """Test startup hook executes without errors."""
        ctx = {}

        with patch("audio_processor.jobs.worker.logger") as mock_logger:
            await startup(ctx)

            # Should log startup message
            mock_logger.info.assert_called_once_with("arq_worker_starting")

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        """Test shutdown hook executes without errors."""
        ctx = {}

        with patch("audio_processor.jobs.worker.logger") as mock_logger:
            await shutdown(ctx)

            # Should log shutdown message
            mock_logger.info.assert_called_once_with("arq_worker_shutting_down")


class TestEnqueueTask:
    """Tests for enqueue_task function."""

    @pytest.mark.asyncio
    async def test_enqueue_task_success(self) -> None:
        """Test enqueue_task successfully enqueues job."""
        mock_redis = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "job_123"
        mock_redis.enqueue_job.return_value = mock_job

        task_name = "process_audio_job"
        args = ("job-abc", {"input": {"file_path": "/tmp/a.wav"}})

        with patch("audio_processor.jobs.worker.logger"):
            job_id = await enqueue_task(mock_redis, task_name, *args)

            assert job_id == "job_123"
            mock_redis.enqueue_job.assert_called_once_with(task_name, *args)

    @pytest.mark.asyncio
    async def test_enqueue_task_with_kwargs(self) -> None:
        """Test enqueue_task with keyword arguments."""
        mock_redis = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "job_456"
        mock_redis.enqueue_job.return_value = mock_job

        task_name = "process_audio_job"
        kwargs = {"job_id": "job-xyz"}

        with patch("audio_processor.jobs.worker.logger"):
            job_id = await enqueue_task(mock_redis, task_name, **kwargs)

            assert job_id == "job_456"
            mock_redis.enqueue_job.assert_called_once_with(task_name, **kwargs)

    @pytest.mark.asyncio
    async def test_enqueue_task_failure(self) -> None:
        """Test enqueue_task raises RuntimeError when job fails to enqueue."""
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.return_value = None

        task_name = "process_audio_job"

        with (
            patch("audio_processor.jobs.worker.logger"),
            pytest.raises(RuntimeError, match="Failed to enqueue task"),
        ):
            await enqueue_task(mock_redis, task_name, "job-1", {})


class TestWorkerSettings:
    """Tests for WorkerSettings configuration."""

    def test_worker_settings_registers_audio_job(self) -> None:
        """Test WorkerSettings registers the audio-processing task."""
        assert hasattr(WorkerSettings, "functions")
        assert process_audio_job in WorkerSettings.functions

    def test_worker_settings_configuration(self) -> None:
        """Test WorkerSettings has correct configuration."""
        assert WorkerSettings.max_jobs == 10
        assert WorkerSettings.job_timeout == 600  # From settings.job_timeout_seconds
        assert (
            WorkerSettings.keep_result == 86400
        )  # From settings.job_result_ttl_seconds
        assert WorkerSettings.max_tries == 3
        assert WorkerSettings.retry_jobs is True
        assert WorkerSettings.health_check_interval == 60

    def test_worker_settings_lifecycle_hooks(self) -> None:
        """Test WorkerSettings has lifecycle hooks configured."""
        assert WorkerSettings.on_startup == startup
        assert WorkerSettings.on_shutdown == shutdown
