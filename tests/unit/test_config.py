"""Unit tests for Settings validators."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from audio_processor.core.config import Settings


class TestEnqueueRequiresRedis:
    """The enqueue_enabled -> redis backend invariant."""

    def test_enqueue_with_memory_backend_rejected(self) -> None:
        """enqueue_enabled with the memory backend fails fast."""
        with pytest.raises(ValidationError):
            Settings(enqueue_enabled=True, job_store_backend="memory")

    def test_enqueue_with_redis_backend_ok(self) -> None:
        """enqueue_enabled with the redis backend is accepted."""
        settings = Settings(enqueue_enabled=True, job_store_backend="redis")
        assert settings.enqueue_enabled is True


class TestAuthRequiresKeys:
    """The auth_required -> at-least-one-key invariant."""

    def test_auth_required_without_keys_rejected(self) -> None:
        """auth_required with no keys fails fast (would reject all requests)."""
        with pytest.raises(ValidationError):
            Settings(auth_required=True, api_keys="")

    def test_auth_required_with_keys_ok(self) -> None:
        """auth_required with keys is accepted and parses the key set."""
        settings = Settings(auth_required=True, api_keys="k1, k2")
        assert settings.api_key_set == {"k1", "k2"}

    def test_api_keys_not_exposed_in_repr(self) -> None:
        """The SecretStr api_keys must not leak via repr/model_dump."""
        settings = Settings(api_keys="super-secret")
        assert "super-secret" not in repr(settings)
        assert "super-secret" not in str(settings.model_dump())
