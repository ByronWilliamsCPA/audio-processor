"""Tests for upload hardening and auth enforcement on API routes."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from audio_processor.api import app
from audio_processor.api.routes import _get_job_store, _stream_upload_to_temp
from audio_processor.core.config import settings

if TYPE_CHECKING:
    from pathlib import Path


class _FakeUpload:
    """Minimal UploadFile stand-in yielding preset chunks from ``read``."""

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = list(chunks)

    async def read(self, size: int = -1) -> bytes:
        """Return the next preset chunk, or empty bytes when exhausted."""
        _ = size
        return self._chunks.pop(0) if self._chunks else b""


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    """Clear the in-memory job store between tests."""
    _get_job_store().clear()


class TestStreamingUploadCap:
    """Tests for the streaming upload size guard."""

    @pytest.mark.asyncio
    async def test_raises_413_when_stream_exceeds_cap(self, tmp_path: Path) -> None:
        """Streaming beyond the byte cap aborts with 413."""
        dest = tmp_path / "out.bin"
        upload = cast("UploadFile", _FakeUpload(b"x" * 100))
        with pytest.raises(HTTPException) as exc:
            await _stream_upload_to_temp(upload, dest, max_bytes=10)
        assert exc.value.status_code == 413

    @pytest.mark.asyncio
    async def test_writes_bytes_within_cap(self, tmp_path: Path) -> None:
        """A stream within the cap is written and the byte count returned."""
        dest = tmp_path / "out.bin"
        upload = cast("UploadFile", _FakeUpload(b"abc", b"de"))
        written = await _stream_upload_to_temp(upload, dest, max_bytes=100)
        assert written == 5
        assert dest.read_bytes() == b"abcde"


class TestTempFileCleanup:
    """Tests that orphaned uploads are removed on failure paths."""

    def test_temp_file_removed_after_validation_failure(
        self,
        client: TestClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A validation failure must not leave the uploaded temp file behind."""
        from audio_processor.core.exceptions import ValidationError

        monkeypatch.setattr(settings, "audio_temp_dir", str(tmp_path))

        with patch("audio_processor.api.routes.AudioConverter") as mock_cls:
            mock = MagicMock()
            mock.validate_file.side_effect = ValidationError(
                "bad", field="file", value="x.xyz"
            )
            mock_cls.return_value = mock

            response = client.post(
                "/api/v1/process",
                files={"file": ("x.wav", b"not audio", "audio/wav")},
            )

        assert response.status_code == 400
        # The streamed temp file should have been cleaned up by the finally block.
        assert list(tmp_path.iterdir()) == []


class TestAuthEnforcement:
    """Tests that auth is enforced on /api/v1 routes when enabled."""

    def test_rejects_request_without_key(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With auth enabled, a request lacking the key is rejected with 401."""
        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", "secret")
        response = client.get(f"/api/v1/status/{uuid.uuid4()}")
        assert response.status_code == 401

    def test_allows_request_with_valid_key(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid key passes auth (unknown job then yields 404, not 401)."""
        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", "secret")
        response = client.get(
            f"/api/v1/status/{uuid.uuid4()}",
            headers={"X-API-Key": "secret"},
        )
        assert response.status_code == 404
