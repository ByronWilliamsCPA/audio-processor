"""Tests for ARQ background job worker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from audio_processor.jobs.worker import (
    WorkerSettings,
    cleanup_old_data,
    enqueue_task,
    example_background_task,
    process_file_upload,
    send_email_task,
    shutdown,
    startup,
)


class TestBackgroundTasks:
    """Tests for background task functions."""

    @pytest.mark.asyncio
    async def test_example_background_task(self) -> None:
        """Test example_background_task executes successfully."""
        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis, "job_id": "test-job-123"}
        user_id = "user_456"
        data = {"action": "export"}

        with patch("audio_processor.jobs.worker.logger"):
            result = await example_background_task(ctx, user_id, data)

            assert result["status"] == "success"
            assert result["user_id"] == user_id
            assert "processed_at" in result

            # Verify Redis was called to store result
            mock_redis.set.assert_called_once()
            call_args = mock_redis.set.call_args[0]
            assert call_args[0] == f"task_result:{user_id}"
            assert call_args[1] == "completed"

    @pytest.mark.asyncio
    async def test_send_email_task(self) -> None:
        """Test send_email_task executes successfully."""
        ctx = {}
        recipient = "test@example.com"
        subject = "Test Email"
        body = "Email body content"

        with patch("audio_processor.jobs.worker.logger"):
            result = await send_email_task(ctx, recipient, subject, body)

            assert result["status"] == "sent"
            assert result["recipient"] == recipient
            assert "sent_at" in result

    @pytest.mark.asyncio
    async def test_process_file_upload_success(self) -> None:
        """Test process_file_upload completes successfully."""
        ctx = {}
        file_id = "file_789"
        file_path = "/data/test.csv"

        with patch("audio_processor.jobs.worker.logger"):
            result = await process_file_upload(ctx, file_id, file_path)

            assert result["status"] == "completed"
            assert result["file_id"] == file_id
            assert "processed_at" in result
            assert "records_processed" in result

    @pytest.mark.asyncio
    async def test_process_file_upload_failure(self) -> None:
        """Test process_file_upload handles exceptions."""
        ctx = {}
        file_id = "file_789"
        file_path = "/data/test.csv"

        with (
            patch(
                "audio_processor.jobs.worker.asyncio.sleep",
                side_effect=RuntimeError("Test error"),
            ),
            patch("audio_processor.jobs.worker.logger"),
            pytest.raises(RuntimeError, match="Test error"),
        ):
            await process_file_upload(ctx, file_id, file_path)

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self) -> None:
        """Test cleanup_old_data task executes."""
        ctx = {}

        with patch("audio_processor.jobs.worker.logger"):
            result = await cleanup_old_data(ctx)

            # Should return count (currently 0 since it's a stub)
            assert isinstance(result, int)
            assert result == 0


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

        task_name = "example_background_task"
        args = ("user_456", {"action": "export"})

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

        task_name = "send_email_task"
        kwargs = {
            "recipient": "test@example.com",
            "subject": "Test",
            "body": "Content",
        }

        with patch("audio_processor.jobs.worker.logger"):
            job_id = await enqueue_task(mock_redis, task_name, **kwargs)

            assert job_id == "job_456"
            mock_redis.enqueue_job.assert_called_once_with(task_name, **kwargs)

    @pytest.mark.asyncio
    async def test_enqueue_task_failure(self) -> None:
        """Test enqueue_task raises RuntimeError when job fails to enqueue."""
        mock_redis = AsyncMock()
        mock_redis.enqueue_job.return_value = None

        task_name = "example_background_task"

        with (
            patch("audio_processor.jobs.worker.logger"),
            pytest.raises(RuntimeError, match="Failed to enqueue task"),
        ):
            await enqueue_task(mock_redis, task_name, "user_123", {})


class TestWorkerSettings:
    """Tests for WorkerSettings configuration."""

    def test_worker_settings_functions(self) -> None:
        """Test WorkerSettings has correct task functions."""
        assert hasattr(WorkerSettings, "functions")
        functions = WorkerSettings.functions

        assert example_background_task in functions
        assert send_email_task in functions
        assert process_file_upload in functions

    def test_worker_settings_cron_jobs(self) -> None:
        """Test WorkerSettings has cron jobs configured."""
        assert hasattr(WorkerSettings, "cron_jobs")
        cron_jobs = WorkerSettings.cron_jobs

        assert len(cron_jobs) == 1

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
