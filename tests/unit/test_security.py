"""Unit tests for API security dependencies (auth + rate limiting)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import SecretStr

from audio_processor.api.security import (
    rate_limit,
    require_api_key,
    reset_rate_limits,
)
from audio_processor.core.config import settings

if TYPE_CHECKING:
    from fastapi import Request


def _fake_request(host: str = "1.2.3.4") -> Request:
    """Build a minimal stand-in Request with a client host."""
    return cast("Request", SimpleNamespace(client=SimpleNamespace(host=host)))


class TestRequireApiKey:
    """Tests for the API-key authentication dependency."""

    @pytest.mark.asyncio
    async def test_open_when_auth_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When auth is disabled the dependency is a no-op."""
        monkeypatch.setattr(settings, "auth_required", False)
        await require_api_key(x_api_key=None)  # should not raise

    @pytest.mark.asyncio
    async def test_rejects_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A missing key is rejected with 401 when auth is required."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", SecretStr("secret-1,secret-2"))
        with pytest.raises(HTTPException) as exc:
            await require_api_key(x_api_key=None)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_wrong_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An incorrect key is rejected with 401."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", SecretStr("secret-1"))
        with pytest.raises(HTTPException) as exc:
            await require_api_key(x_api_key="nope")
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_valid_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A valid key passes authentication."""
        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", SecretStr("secret-1,secret-2"))
        await require_api_key(x_api_key="secret-2")  # should not raise

    @pytest.mark.asyncio
    async def test_misconfiguration_returns_500(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auth required but no keys configured is a 500 (server misconfig)."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "api_keys", SecretStr(""))
        with pytest.raises(HTTPException) as exc:
            await require_api_key(x_api_key="anything")
        assert exc.value.status_code == 500


class TestRateLimit:
    """Tests for the rate-limiting dependency."""

    @pytest.mark.asyncio
    async def test_noop_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No limiting occurs when the feature is disabled."""
        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        reset_rate_limits()
        for _ in range(100):
            await rate_limit(_fake_request(), x_api_key="k")  # never raises

    @pytest.mark.asyncio
    async def test_allows_up_to_limit_then_blocks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Requests up to the limit pass; the next is rejected with 429."""
        from fastapi import HTTPException

        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "rate_limit_requests", 2)
        monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
        reset_rate_limits()

        await rate_limit(_fake_request(), x_api_key="client-a")
        await rate_limit(_fake_request(), x_api_key="client-a")
        with pytest.raises(HTTPException) as exc:
            await rate_limit(_fake_request(), x_api_key="client-a")
        assert exc.value.status_code == 429
        assert "Retry-After" in (exc.value.headers or {})

    @pytest.mark.asyncio
    async def test_limit_is_per_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Separate clients have independent budgets."""
        monkeypatch.setattr(settings, "rate_limit_enabled", True)
        monkeypatch.setattr(settings, "rate_limit_requests", 1)
        monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
        reset_rate_limits()

        await rate_limit(_fake_request(), x_api_key="client-a")
        # Different client, fresh budget -> must not raise.
        await rate_limit(_fake_request(), x_api_key="client-b")
