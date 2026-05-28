"""Tests for jobs package initialization."""

from __future__ import annotations

import audio_processor.jobs


class TestJobsPackage:
    """Tests for jobs package."""

    def test_jobs_package_imports(self) -> None:
        """Test jobs package can be imported."""
        assert hasattr(audio_processor.jobs, "__all__")

    def test_jobs_package_all_contains_process_audio_job(self) -> None:
        """Test jobs package __all__ contains expected exports."""
        assert "process_audio_job" in audio_processor.jobs.__all__
