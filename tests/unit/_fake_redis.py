# SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamshome.family>
#
# SPDX-License-Identifier: MIT
"""Shared async Redis stand-in for job-store tests.

Models the hash commands used by :class:`audio_processor.core.job_store.RedisJobStore`
(``hset``/``hgetall``/``expire``/``delete`` plus a buffered ``pipeline``). Set
``decode_responses=False`` to make ``hgetall`` return ``bytes`` keys and values,
exercising the store's bytes-decoding branch the way an undecoded real client
would.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class _FakePipeline:
    """Buffered command pipeline mirroring redis-py's ``transaction=True`` usage.

    Commands are recorded synchronously (each returns ``self``) and applied in
    order on :meth:`execute`, matching the atomic MULTI/EXEC contract the store
    relies on.
    """

    def __init__(self, redis: FakeRedis) -> None:
        """Bind the pipeline to its backing fake.

        Args:
            redis: The fake connection the buffered commands apply to.
        """
        self._redis = redis
        self._ops: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def delete(self, key: str) -> _FakePipeline:
        """Buffer a ``DELETE``."""
        self._ops.append(("delete", (key,), {}))
        return self

    def hset(self, key: str, *, mapping: Mapping[str, str]) -> _FakePipeline:
        """Buffer an ``HSET`` with a field mapping."""
        self._ops.append(("hset", (key,), {"mapping": mapping}))
        return self

    def expire(self, key: str, ttl: int) -> _FakePipeline:
        """Buffer an ``EXPIRE``."""
        self._ops.append(("expire", (key, ttl), {}))
        return self

    async def execute(self) -> list[object]:
        """Apply all buffered commands in order and return their results."""
        results: list[object] = []
        for name, args, kwargs in self._ops:
            method = getattr(self._redis, name)
            results.append(await method(*args, **kwargs))
        self._ops.clear()
        return results


class FakeRedis:
    """Minimal async Redis stand-in backed by per-key hashes."""

    def __init__(self, *, decode_responses: bool = True) -> None:
        """Initialize an empty fake.

        Args:
            decode_responses: When false, ``hgetall`` returns ``bytes`` keys and
                values, mirroring a client created without response decoding.
        """
        self._hashes: dict[str, dict[str, str]] = {}
        self._decode_responses = decode_responses
        self.last_ex: int | None = None

    def _encode(self, value: str) -> str | bytes:
        """Return ``value`` as ``str`` or ``bytes`` per ``decode_responses``."""
        return value if self._decode_responses else value.encode()

    async def hset(self, key: str, *, mapping: Mapping[str, str]) -> int:
        """Merge ``mapping`` into the hash at ``key``; return fields written."""
        self._hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hgetall(self, key: str) -> dict[str | bytes, str | bytes]:
        """Return all fields of the hash at ``key`` (empty dict if absent)."""
        fields = self._hashes.get(key)
        if not fields:
            return {}
        return {self._encode(f): self._encode(v) for f, v in fields.items()}

    async def expire(self, key: str, ttl: int) -> bool:
        """Record the requested TTL; report whether the key exists."""
        self.last_ex = ttl
        return key in self._hashes

    async def delete(self, key: str) -> int:
        """Remove the hash at ``key``; return the number of keys removed."""
        return 1 if self._hashes.pop(key, None) is not None else 0

    def pipeline(self, *, transaction: bool = True) -> _FakePipeline:
        """Return a buffered pipeline (the ``transaction`` flag is accepted)."""
        _ = transaction
        return _FakePipeline(self)
