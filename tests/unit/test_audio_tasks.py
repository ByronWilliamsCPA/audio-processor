"""Unit tests for the audio processing worker task.

These tests exercise ``process_audio_job`` end to end with the external
services (converter, quality assessor, Deepgram, artifact generator) mocked at
their boundaries, and a fake Redis backing the shared job store. They verify
that job state actually transitions to COMPLETED/FAILED in the store the API
reads from -- the disconnect this refactor fixes.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from audio_processor.core.exceptions import AudioProcessorError, ValidationError
from audio_processor.core.job_store import job_key
from audio_processor.core.models import (
    AudioQualityMetrics,
    QualityLevel,
    Speaker,
    TranscriptionMetadata,
    TranscriptionResult,
    Utterance,
)
from audio_processor.jobs.audio_tasks import process_audio_job

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class FakeRedis:
    """Minimal async Redis stand-in supporting get/set with TTL."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        """Return the stored value for ``key`` or ``None``."""
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store ``value`` under ``key`` (TTL ignored in the fake)."""
        _ = ex
        self.store[key] = value


def _quality_metrics() -> AudioQualityMetrics:
    """Build a representative quality-metrics model."""
    return AudioQualityMetrics(
        snr_db=20.0,
        silence_ratio=0.1,
        clipping_ratio=0.0,
        peak_amplitude=0.8,
        rms_level_db=-18.0,
        duration_seconds=12.0,
        sample_rate=16000,
        channels=1,
        quality_score=0.9,
        quality_level=QualityLevel.GOOD,
        warnings=(),
    )


def _transcription_result() -> TranscriptionResult:
    """Build a small transcription result with one speaker/utterance."""
    return TranscriptionResult(
        transcript="hello world",
        utterances=(
            Utterance(
                speaker=0,
                start=0.0,
                end=1.0,
                text="hello world",
                confidence=0.95,
                words=(),
            ),
        ),
        speakers=(Speaker(id=0, label="Speaker 1", total_duration=1.0),),
        words=(),
        summary="a short summary",
        metadata=TranscriptionMetadata(
            duration_seconds=12.0,
            word_count=2,
            confidence_mean=0.95,
            confidence_min=0.9,
            cost_usd=Decimal("0.0010"),
        ),
    )


@pytest.fixture
def input_file(tmp_path: Path) -> Path:
    """Create a real (empty) input file for the job."""
    path = tmp_path / "input.wav"
    path.write_bytes(b"RIFF0000WAVE")
    return path


@pytest.fixture
def patched_services(tmp_path: Path) -> Iterator[MagicMock]:
    """Patch converter/assessor/Deepgram/artifacts at their boundaries.

    Yields the Deepgram client class mock so individual tests can override the
    transcription behaviour (e.g. to simulate a missing API key).
    """
    converted = tmp_path / "converted.wav"
    converted.write_bytes(b"RIFF0000WAVE")

    converter = MagicMock()
    converter.is_video.return_value = False
    converter.convert_for_asr.return_value = converted

    assessor = MagicMock()
    assessor.assess.return_value = _quality_metrics()

    dg_instance = MagicMock()
    dg_instance.transcribe.return_value = _transcription_result()
    dg_cls = MagicMock(return_value=dg_instance)

    generator = MagicMock()
    generator.generate_all.return_value = {"transcript.txt": "hello world"}

    with (
        patch(
            "audio_processor.jobs.audio_tasks.AudioConverter",
            return_value=converter,
        ),
        patch(
            "audio_processor.jobs.audio_tasks.QualityAssessor",
            return_value=assessor,
        ),
        patch(
            "audio_processor.services.deepgram_client.DeepgramTranscriptionClient",
            dg_cls,
        ),
        patch(
            "audio_processor.services.transcript_formatter.ArtifactGenerator",
            return_value=generator,
        ),
    ):
        yield dg_cls


class TestProcessAudioJob:
    """Tests for the main ARQ audio-processing task."""

    @pytest.mark.asyncio
    async def test_completes_and_persists_result_to_store(
        self,
        input_file: Path,
        patched_services: MagicMock,
    ) -> None:
        """A successful run should mark the job COMPLETED with result+artifacts."""
        assert patched_services is not None
        redis = FakeRedis()
        ctx = {"redis": redis}
        job_data = {"input": {"file_path": str(input_file)}}

        result = await process_audio_job(ctx, "job1", job_data)  # type: ignore[arg-type]

        assert result["status"] == "completed"
        stored = json.loads(redis.store[job_key("job1")])
        assert stored["status"] == "completed"
        assert stored["result"]["transcription"]["transcript"] == "hello world"
        assert stored["artifacts"] == {"transcript.txt": "hello world"}
        assert stored["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_missing_file_marks_job_failed(
        self,
        patched_services: MagicMock,
    ) -> None:
        """A missing input file should raise and mark the job FAILED in the store."""
        assert patched_services is not None
        redis = FakeRedis()
        ctx = {"redis": redis}
        job_data = {"input": {"file_path": "/nonexistent/audio.wav"}}

        with pytest.raises(ValidationError):
            await process_audio_job(ctx, "job2", job_data)  # type: ignore[arg-type]

        stored = json.loads(redis.store[job_key("job2")])
        assert stored["status"] == "failed"
        assert stored["error"]

    @pytest.mark.asyncio
    async def test_missing_deepgram_key_completes_without_transcription(
        self,
        input_file: Path,
        patched_services: MagicMock,
    ) -> None:
        """If Deepgram is unconfigured, the job still completes (no transcription)."""
        from audio_processor.core.exceptions import ConfigurationError

        patched_services.side_effect = ConfigurationError("no key")
        redis = FakeRedis()
        ctx = {"redis": redis}
        job_data = {"input": {"file_path": str(input_file)}}

        result = await process_audio_job(ctx, "job3", job_data)  # type: ignore[arg-type]

        assert result["status"] == "completed"
        stored = json.loads(redis.store[job_key("job3")])
        assert stored["status"] == "completed"
        assert stored["result"]["transcription"] is None
        assert "warning" in stored["result"]

    @pytest.mark.asyncio
    async def test_unexpected_error_wraps_and_marks_failed(
        self,
        input_file: Path,
    ) -> None:
        """A non-domain error is wrapped as AudioProcessorError and marks FAILED."""
        redis = FakeRedis()
        ctx = {"redis": redis}
        job_data = {"input": {"file_path": str(input_file)}}

        with (
            patch(
                "audio_processor.jobs.audio_tasks.AudioConverter",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(AudioProcessorError),
        ):
            await process_audio_job(ctx, "job4", job_data)  # type: ignore[arg-type]

        stored = json.loads(redis.store[job_key("job4")])
        assert stored["status"] == "failed"
        assert stored["error"]

    @pytest.mark.asyncio
    async def test_artifact_failure_still_completes(
        self,
        input_file: Path,
        patched_services: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Artifact generation failure should not fail an otherwise-complete job."""
        assert patched_services is not None
        failing = MagicMock()
        failing.generate_all.side_effect = AudioProcessorError("boom")
        monkeypatch.setattr(
            "audio_processor.services.transcript_formatter.ArtifactGenerator",
            MagicMock(return_value=failing),
        )
        redis = FakeRedis()
        ctx = {"redis": redis}
        job_data = {"input": {"file_path": str(input_file)}}

        result = await process_audio_job(ctx, "job5", job_data)  # type: ignore[arg-type]

        assert result["status"] == "completed"
        stored = json.loads(redis.store[job_key("job5")])
        assert stored["status"] == "completed"
        assert stored["artifacts"] == {}
