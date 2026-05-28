"""Unit tests for core data models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from audio_processor.core.models import (
    AudioFormat,
    AudioJob,
    AudioJobInput,
    AudioQualityMetrics,
    JobStatus,
    ProcessAudioResponse,
    QualityLevel,
    Speaker,
    TranscriptionMetadata,
    TranscriptionResult,
    Utterance,
    Word,
)


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.PREPROCESSING.value == "preprocessing"
        assert JobStatus.TRANSCRIBING.value == "transcribing"
        assert JobStatus.POSTPROCESSING.value == "postprocessing"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


class TestAudioFormat:
    """Tests for AudioFormat enum."""

    def test_audio_formats(self) -> None:
        """Test audio format values."""
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.M4A.value == "m4a"
        assert AudioFormat.FLAC.value == "flac"

    def test_video_formats(self) -> None:
        """Test video format values."""
        assert AudioFormat.MP4.value == "mp4"
        assert AudioFormat.MOV.value == "mov"
        assert AudioFormat.AVI.value == "avi"


class TestWord:
    """Tests for Word model."""

    def test_word_creation(self) -> None:
        """Test basic word creation."""
        word = Word(
            word="hello",
            start=0.0,
            end=0.5,
            confidence=0.95,
        )
        assert word.word == "hello"
        assert word.start == 0.0
        assert word.end == 0.5
        assert word.confidence == 0.95
        assert word.speaker is None

    def test_word_with_speaker(self) -> None:
        """Test word with speaker diarization."""
        word = Word(
            word="world",
            start=0.5,
            end=1.0,
            confidence=0.92,
            speaker=0,
            punctuated_word="World!",
        )
        assert word.speaker == 0
        assert word.punctuated_word == "World!"


class TestUtterance:
    """Tests for Utterance model."""

    def test_utterance_creation(self) -> None:
        """Test basic utterance creation."""
        utterance = Utterance(
            speaker=0,
            start=0.0,
            end=2.5,
            text="Hello, world!",
            confidence=0.95,
        )
        assert utterance.speaker == 0
        assert utterance.text == "Hello, world!"
        assert utterance.confidence == 0.95

    def test_utterance_duration(self) -> None:
        """Test utterance duration calculation."""
        utterance = Utterance(
            speaker=1,
            start=1.0,
            end=3.5,
            text="Test",
            confidence=0.9,
        )
        assert utterance.duration == 2.5


class TestSpeaker:
    """Tests for Speaker model."""

    def test_speaker_creation(self) -> None:
        """Test speaker creation."""
        speaker = Speaker(
            id=0,
            label="Speaker 1",
            total_duration=30.0,
            utterance_count=5,
        )
        assert speaker.id == 0
        assert speaker.label == "Speaker 1"
        assert speaker.total_duration == 30.0
        assert speaker.utterance_count == 5


class TestAudioQualityMetrics:
    """Tests for AudioQualityMetrics model."""

    def test_quality_metrics_creation(self) -> None:
        """Test quality metrics creation."""
        metrics = AudioQualityMetrics(
            snr_db=25.0,
            silence_ratio=0.1,
            clipping_ratio=0.0,
            peak_amplitude=0.95,
            rms_level_db=-20.0,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            quality_score=0.9,
            quality_level=QualityLevel.EXCELLENT,
        )
        assert metrics.snr_db == 25.0
        assert metrics.quality_level == QualityLevel.EXCELLENT
        assert len(metrics.warnings) == 0

    def test_quality_metrics_with_warnings(self) -> None:
        """Test quality metrics with warnings."""
        metrics = AudioQualityMetrics(
            snr_db=8.0,
            silence_ratio=0.6,
            clipping_ratio=0.05,
            peak_amplitude=1.0,
            rms_level_db=-15.0,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
            quality_score=0.3,
            quality_level=QualityLevel.POOR,
            warnings=("Low SNR", "High silence"),
        )
        assert len(metrics.warnings) == 2


class TestTranscriptionMetadata:
    """Tests for TranscriptionMetadata model."""

    def test_metadata_creation(self) -> None:
        """Test metadata creation."""
        metadata = TranscriptionMetadata(
            duration_seconds=60.0,
            word_count=150,
            confidence_mean=0.92,
            confidence_min=0.75,
            model="nova-2",
            language="en",
        )
        assert metadata.duration_seconds == 60.0
        assert metadata.word_count == 150
        assert metadata.model == "nova-2"

    def test_metadata_with_cost(self) -> None:
        """Test metadata with cost information."""
        metadata = TranscriptionMetadata(
            duration_seconds=3600.0,
            word_count=5000,
            confidence_mean=0.9,
            confidence_min=0.7,
            processing_time_seconds=45.0,
            cost_usd=Decimal("0.35"),
        )
        assert metadata.cost_usd == Decimal("0.35")
        assert metadata.processing_time_seconds == 45.0


class TestTranscriptionResult:
    """Tests for TranscriptionResult model."""

    def test_result_creation(self) -> None:
        """Test basic result creation."""
        result = TranscriptionResult(
            transcript="Hello, world!",
            metadata=TranscriptionMetadata(
                duration_seconds=1.0,
                word_count=2,
                confidence_mean=0.95,
                confidence_min=0.9,
            ),
        )
        assert result.transcript == "Hello, world!"
        assert len(result.utterances) == 0
        assert len(result.speakers) == 0


class TestAudioJobInput:
    """Tests for AudioJobInput model."""

    def test_input_creation(self) -> None:
        """Test job input creation."""
        job_input = AudioJobInput(
            file_path="/tmp/audio.wav",
            original_filename="audio.wav",
            file_size_bytes=1024000,
            content_type="audio/wav",
        )
        assert job_input.file_path == "/tmp/audio.wav"
        assert job_input.enable_diarization is True
        assert job_input.enable_summarization is True
        assert job_input.language == "en"


class TestAudioJob:
    """Tests for AudioJob model."""

    def test_job_creation(self) -> None:
        """Test job creation."""
        job = AudioJob(
            input=AudioJobInput(
                file_path="/tmp/audio.wav",
                original_filename="audio.wav",
                file_size_bytes=1024000,
                content_type="audio/wav",
            ),
        )
        assert isinstance(job.id, UUID)
        assert job.status == JobStatus.PENDING
        assert job.result is None
        assert job.error is None
        assert isinstance(job.created_at, datetime)


class TestProcessAudioResponse:
    """Tests for ProcessAudioResponse model."""

    def test_response_creation(self) -> None:
        """Test response creation."""
        from uuid import uuid4

        job_id = uuid4()
        response = ProcessAudioResponse(
            job_id=job_id,
            status=JobStatus.QUEUED,
            status_url="http://localhost:8000/api/v1/status/" + str(job_id),
            message="Audio queued for processing",
        )
        assert response.job_id == job_id
        assert response.status == JobStatus.QUEUED
