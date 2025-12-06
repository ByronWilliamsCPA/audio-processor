"""Tests for jobs package initialization."""

from __future__ import annotations

import audio_processor.jobs


class TestJobsPackage:
    """Tests for jobs package."""

    def test_jobs_package_imports(self) -> None:
        """Test jobs package can be imported."""
        assert hasattr(audio_processor.jobs, "__all__")

    def test_jobs_package_all_is_empty(self) -> None:
        """Test jobs package __all__ is empty list."""
        assert audio_processor.jobs.__all__ == []
