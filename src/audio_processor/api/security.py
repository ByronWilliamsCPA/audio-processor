"""API security dependencies: API-key authentication and rate limiting.

Both controls are gated by configuration and default to disabled, so they are
no-ops unless explicitly enabled:

- :func:`require_api_key` enforces a valid ``X-API-Key`` header when
  ``auth_required`` is set.
- :func:`rate_limit` applies a per-client fixed-window limit when
  ``rate_limit_enabled`` is set.

The rate limiter is process-local (in-memory). For multi-process or multi-host
deployments, enforce limits at a shared layer (gateway, or a Redis-backed
limiter) in addition to this safety net.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import TYPE_CHECKING, Annotated

from fastapi import Header, HTTPException, Request, status

from audio_processor.core.config import settings

if TYPE_CHECKING:
    from collections.abc import Mapping

API_KEY_HEADER = "X-API-Key"

# Per-identifier fixed window: identifier -> (request_count, window_start_monotonic).
_RATE_WINDOWS: dict[str, tuple[int, float]] = {}

# Soft cap on tracked identifiers. When exceeded, fully-expired windows are
# evicted opportunistically so a flood of unique clients (e.g. distinct source
# IPs) cannot grow the map without bound.
_MAX_TRACKED_CLIENTS = 10_000


def reset_rate_limits() -> None:
    """Clear all rate-limit state (intended for tests)."""
    _RATE_WINDOWS.clear()


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Authenticate a request via the ``X-API-Key`` header.

    No-op when ``auth_required`` is false. When enabled, the supplied key is
    compared in constant time against the configured set.

    Args:
        x_api_key: Value of the ``X-API-Key`` request header, if present.

    Raises:
        HTTPException: 500 if auth is required but no keys are configured;
            401 if the key is missing or invalid.
    """
    if not settings.auth_required:
        return

    keys = settings.api_key_set
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is required but no API keys are configured",
        )

    # Compare against every key (no short-circuit) to avoid leaking, via
    # response timing, how many candidate keys were checked before a match.
    matched = False
    if x_api_key is not None:
        for key in keys:
            if hmac.compare_digest(x_api_key, key):
                matched = True

    if not matched:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API-Key"},
        )


def _client_identifier(request: Request, x_api_key: str | None) -> str:
    """Derive a rate-limit identifier from the API key or client address.

    Args:
        request: The incoming request.
        x_api_key: The API key header value, if present.

    Returns:
        A stable identifier for the caller.
    """
    if x_api_key:
        # Hash the key so raw secrets are never used as in-memory map keys.
        digest = hashlib.sha256(x_api_key.encode()).hexdigest()
        return f"key:{digest}"
    client = request.client
    return f"ip:{client.host}" if client else "anonymous"


async def rate_limit(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> None:
    """Apply a per-client fixed-window rate limit.

    No-op when ``rate_limit_enabled`` is false.

    Args:
        request: The incoming request (used for the client address fallback).
        x_api_key: The API key header value, if present.

    Raises:
        HTTPException: 429 when the caller exceeds the configured limit, with a
            ``Retry-After`` header.
    """
    if not settings.rate_limit_enabled:
        return

    identifier = _client_identifier(request, x_api_key)
    now = time.monotonic()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests

    # Bound memory: first drop fully-expired windows, then, if still over the
    # cap (a flood of unique *active* clients), evict the oldest windows so the
    # map size is hard-capped rather than merely trimmed of expired entries.
    if len(_RATE_WINDOWS) > _MAX_TRACKED_CLIENTS:
        expired = [key for key, (_, s) in _RATE_WINDOWS.items() if now - s >= window]
        for key in expired:
            del _RATE_WINDOWS[key]
        if len(_RATE_WINDOWS) > _MAX_TRACKED_CLIENTS:
            overflow = len(_RATE_WINDOWS) - _MAX_TRACKED_CLIENTS
            oldest = sorted(_RATE_WINDOWS, key=lambda k: _RATE_WINDOWS[k][1])[:overflow]
            for key in oldest:
                del _RATE_WINDOWS[key]

    count, start = _RATE_WINDOWS.get(identifier, (0, now))
    if now - start >= window:
        count, start = 0, now
    count += 1
    _RATE_WINDOWS[identifier] = (count, start)

    if count > limit:
        retry_after = max(1, int(window - (now - start)))
        headers: Mapping[str, str] = {"Retry-After": str(retry_after)}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers=dict(headers),
        )
