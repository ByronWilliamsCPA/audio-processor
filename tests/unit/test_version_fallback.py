"""Tests for package version derivation and its metadata-absent fallback.

The package and API modules derive their version from installed package
metadata via ``importlib.metadata.version`` and fall back to ``"unknown"``
when the distribution is not installed (``PackageNotFoundError``). These
tests cover that fallback branch, which is otherwise unreachable while the
package is installed in editable mode during the test run.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


def _patch_version_to_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``importlib.metadata.version`` raise only for ``audio-processor``.

    Other distributions still resolve normally so that re-importing the
    modules under test does not perturb unrelated metadata lookups.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
    """
    real: Callable[[str], str] = importlib.metadata.version

    def _fake(name: str) -> str:
        if name == "audio-processor":
            raise importlib.metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(importlib.metadata, "version", _fake)


class TestVersionFallback:
    """Version derivation falls back to ``"unknown"`` when metadata is absent."""

    def test_root_version_falls_back_to_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``audio_processor.__version__`` is ``"unknown"`` without metadata."""
        import audio_processor

        _patch_version_to_raise(monkeypatch)
        try:
            importlib.reload(audio_processor)
            assert audio_processor.__version__ == "unknown"
        finally:
            monkeypatch.undo()
            importlib.reload(audio_processor)

    def test_api_app_version_falls_back_to_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``audio_processor.api.APP_VERSION`` is ``"unknown"`` without metadata."""
        import audio_processor.api as api_module

        _patch_version_to_raise(monkeypatch)
        try:
            importlib.reload(api_module)
            assert api_module.APP_VERSION == "unknown"
        finally:
            monkeypatch.undo()
            importlib.reload(api_module)
