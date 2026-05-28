"""Unit tests for audio processing API routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from audio_processor.api import app
from audio_processor.api.routes import _get_job_store
from audio_processor.core.models import JobStatus
from audio_processor.services.audio_converter import AudioInfo


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_job_store() -> None:
    """Clear the in-memory job store between tests."""
    store = _get_job_store()
    store.clear()


@pytest.fixture
def fake_audio_info() -> AudioInfo:
    """Return a fake AudioInfo for tests that don't need real FFprobe."""
    return AudioInfo(
        duration_seconds=120.0,
        sample_rate=44100,
        channels=2,
        codec="pcm_s16le",
        bit_rate=1411200,
        format_name="wav",
        is_video=False,
    )


@pytest.fixture
def queued_job_id() -> str:
    """Inject a pre-queued job into the store and return its ID."""
    job_id = str(uuid.uuid4())
    store = _get_job_store()
    store[job_id] = {
        "id": job_id,
        "status": JobStatus.QUEUED.value,
        "input": {},
        "progress": None,
        "result": None,
        "error": None,
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "audio_info": {},
    }
    return job_id


@pytest.fixture
def completed_job_id() -> str:
    """Inject a completed job with result and artifacts into the store."""
    job_id = str(uuid.uuid4())
    store = _get_job_store()
    store[job_id] = {
        "id": job_id,
        "status": JobStatus.COMPLETED.value,
        "input": {},
        "progress": None,
        "result": {
            "language": "en",
            "word_count": 200,
            "speaker_count": 2,
            "duration_ms": 120000,
        },
        "error": None,
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "artifacts": {
            "docling_dom.json": b'{"type":"doc"}',
            "transcript.txt": b"Hello world",
        },
        "quality": {"quality_level": "good"},
    }
    return job_id


class TestProcessAudioRoute:
    """Tests for POST /api/v1/process."""

    def test_returns_4xx_when_no_filename(self, client: TestClient) -> None:
        """Uploading a file with an empty filename should be rejected.

        FastAPI intercepts an empty filename at form validation (422), before
        our 400 guard runs -- the exact status depends on how the framework
        parses the multipart header.
        """
        response = client.post(
            "/api/v1/process",
            files={"file": ("", b"fake content", "audio/wav")},
        )
        assert response.status_code in (400, 422)

    def test_returns_413_when_file_too_large(self, client: TestClient) -> None:
        """Request with content-length exceeding the limit should return 413."""
        from audio_processor.core.config import settings

        oversized = settings.max_file_size_bytes + 1
        response = client.post(
            "/api/v1/process",
            files={"file": ("test.wav", b"fake content", "audio/wav")},
            headers={"content-length": str(oversized)},
        )
        assert response.status_code == 413

    def test_returns_400_when_file_fails_validation(self, client: TestClient) -> None:
        """Uploading a file that fails audio validation should return 400."""
        from audio_processor.core.exceptions import ValidationError

        with patch("audio_processor.api.routes.AudioConverter") as mock_converter_cls:
            mock_converter = MagicMock()
            mock_converter.validate_file.side_effect = ValidationError(
                "Unsupported format",
                field="file",
                value="test.xyz",
            )
            mock_converter_cls.return_value = mock_converter

            response = client.post(
                "/api/v1/process",
                files={"file": ("test.xyz", b"not audio", "application/octet-stream")},
            )

        assert response.status_code == 400

    def test_returns_202_and_job_id_for_valid_file(
        self,
        client: TestClient,
        fake_audio_info: AudioInfo,
    ) -> None:
        """Valid audio upload should be accepted with 202 and a job_id."""
        with patch("audio_processor.api.routes.AudioConverter") as mock_converter_cls:
            mock_converter = MagicMock()
            mock_converter.validate_file.return_value = fake_audio_info
            mock_converter_cls.return_value = mock_converter

            response = client.post(
                "/api/v1/process",
                files={
                    "file": ("test.wav", b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio/wav")
                },
                data={"enable_diarization": "true", "language": "en"},
            )

        assert response.status_code == 202
        body = response.json()
        assert "job_id" in body
        assert body["status"] == JobStatus.QUEUED.value
        assert "status_url" in body

    def test_stores_job_in_store_after_valid_upload(
        self,
        client: TestClient,
        fake_audio_info: AudioInfo,
    ) -> None:
        """A successful upload should persist the job in the job store."""
        with patch("audio_processor.api.routes.AudioConverter") as mock_converter_cls:
            mock_converter = MagicMock()
            mock_converter.validate_file.return_value = fake_audio_info
            mock_converter_cls.return_value = mock_converter

            response = client.post(
                "/api/v1/process",
                files={"file": ("audio.mp3", b"ID3\x00", "audio/mpeg")},
            )

        assert response.status_code == 202
        job_id = response.json()["job_id"]
        store = _get_job_store()
        assert str(job_id) in store

    def test_returns_500_on_unexpected_error(self, client: TestClient) -> None:
        """An unexpected error in processing should return 500."""
        with patch("audio_processor.api.routes.AudioConverter") as mock_converter_cls:
            mock_converter_cls.side_effect = RuntimeError("disk full")

            response = client.post(
                "/api/v1/process",
                files={"file": ("test.wav", b"data", "audio/wav")},
            )

        assert response.status_code == 500


class TestGetJobStatusRoute:
    """Tests for GET /api/v1/status/{job_id}."""

    def test_returns_404_for_unknown_job(self, client: TestClient) -> None:
        """Status check for a non-existent job should return 404."""
        response = client.get(f"/api/v1/status/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_returns_status_for_queued_job(
        self, client: TestClient, queued_job_id: str
    ) -> None:
        """Status for a queued job should return QUEUED with no result_url."""
        response = client.get(f"/api/v1/status/{queued_job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.QUEUED.value
        assert body["result_url"] is None

    def test_returns_result_url_for_completed_job(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """Status for a completed job should include a result_url."""
        response = client.get(f"/api/v1/status/{completed_job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == JobStatus.COMPLETED.value
        assert body["result_url"] is not None
        assert completed_job_id in body["result_url"]

    def test_returns_progress_when_present(self, client: TestClient) -> None:
        """When progress data is stored, it should be returned in the response."""
        job_id = str(uuid.uuid4())
        store = _get_job_store()
        store[job_id] = {
            "status": JobStatus.TRANSCRIBING.value,
            "progress": {
                "stage": "transcribing",
                "percent_complete": 50,
                "message": "Halfway there",
                "started_at": datetime.now(UTC).isoformat(),
            },
            "result": None,
            "error": None,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
        }

        response = client.get(f"/api/v1/status/{job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["progress"] is not None
        assert body["progress"]["stage"] == "transcribing"
        assert body["progress"]["percent_complete"] == 50

    def test_returns_error_field_when_job_failed(self, client: TestClient) -> None:
        """A failed job status should include the error message."""
        job_id = str(uuid.uuid4())
        store = _get_job_store()
        store[job_id] = {
            "status": JobStatus.FAILED.value,
            "progress": None,
            "result": None,
            "error": "FFmpeg not found",
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        }

        response = client.get(f"/api/v1/status/{job_id}")
        assert response.status_code == 200
        assert response.json()["error"] == "FFmpeg not found"


class TestGetJobResultsRoute:
    """Tests for GET /api/v1/results/{job_id}."""

    def test_returns_404_for_unknown_job(self, client: TestClient) -> None:
        """Results for a non-existent job should return 404."""
        response = client.get(f"/api/v1/results/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_returns_400_when_job_not_completed(
        self, client: TestClient, queued_job_id: str
    ) -> None:
        """Fetching results of a queued job should return 400."""
        response = client.get(f"/api/v1/results/{queued_job_id}")
        assert response.status_code == 400
        assert "not completed" in response.json()["detail"].lower()

    def test_returns_404_when_no_result_stored(self, client: TestClient) -> None:
        """A completed job with no result dict should return 404 on results."""
        job_id = str(uuid.uuid4())
        store = _get_job_store()
        store[job_id] = {
            "status": JobStatus.COMPLETED.value,
            "result": None,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        }

        response = client.get(f"/api/v1/results/{job_id}")
        assert response.status_code == 404

    def test_returns_result_for_completed_job(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """Results for a completed job should include transcription and artifacts."""
        response = client.get(f"/api/v1/results/{completed_job_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["job_id"] == completed_job_id
        assert body["status"] == JobStatus.COMPLETED.value
        assert "artifacts" in body
        assert "docling_dom.json" in body["artifacts"]["docling_dom"]


class TestGetArtifactRoute:
    """Tests for GET /api/v1/artifacts/{job_id}/{artifact_name}."""

    def test_returns_404_for_unknown_job(self, client: TestClient) -> None:
        """Artifact download for a non-existent job should return 404."""
        response = client.get(f"/api/v1/artifacts/{uuid.uuid4()}/transcript.txt")
        assert response.status_code == 404

    def test_returns_400_when_job_not_completed(
        self, client: TestClient, queued_job_id: str
    ) -> None:
        """Artifact download for a queued job should return 400."""
        response = client.get(f"/api/v1/artifacts/{queued_job_id}/transcript.txt")
        assert response.status_code == 400

    def test_returns_400_for_invalid_artifact_name(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """Requesting an unknown artifact name should return 400."""
        response = client.get(f"/api/v1/artifacts/{completed_job_id}/unknown.pdf")
        assert response.status_code == 400
        assert "unknown.pdf" in response.json()["detail"]

    def test_returns_404_when_no_artifacts_on_job(self, client: TestClient) -> None:
        """A completed job with no artifacts dict should return 404."""
        job_id = str(uuid.uuid4())
        store = _get_job_store()
        store[job_id] = {
            "status": JobStatus.COMPLETED.value,
            "artifacts": None,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
        }

        response = client.get(f"/api/v1/artifacts/{job_id}/transcript.txt")
        assert response.status_code == 404

    def test_returns_404_when_specific_artifact_missing(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """Requesting a valid artifact name that wasn't generated should return 404."""
        response = client.get(f"/api/v1/artifacts/{completed_job_id}/transcript.srt")
        assert response.status_code == 404

    def test_returns_artifact_content_with_correct_type(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """A present artifact should be returned with the correct content type."""
        response = client.get(f"/api/v1/artifacts/{completed_job_id}/transcript.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_returns_json_artifact_with_correct_type(
        self, client: TestClient, completed_job_id: str
    ) -> None:
        """The Docling DOM artifact should be returned as application/json."""
        response = client.get(f"/api/v1/artifacts/{completed_job_id}/docling_dom.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
