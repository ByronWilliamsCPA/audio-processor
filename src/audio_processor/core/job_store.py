"""Job state storage abstraction.

This module provides a single source of truth for audio-processing job state,
shared by the HTTP API layer and the ARQ worker. Two backends are provided:

- :class:`InMemoryJobStore`: process-local dict, used for development and tests.
  It also exposes a small synchronous mapping interface (``store[job_id] = ...``,
  ``job_id in store``, ``store.clear()``) for ergonomic direct injection.
- :class:`RedisJobStore`: JSON-in-Redis backend keyed by ``job:{job_id}``, used in
  production so the API and the (separate-process) worker observe the same state.

Both backends share the same key scheme and record shape so that a job created
by the API is visible to the worker and vice versa.
"""

from __future__ import annotations

import abc
import json
from typing import TYPE_CHECKING

from audio_processor.core.config import settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

# A job record is a JSON-serializable mapping. Values are intentionally broad
# (object) because records carry mixed content (status strings, nested input
# dicts, progress dicts, results, ISO timestamps).
JobRecord = dict[str, object]

JOB_KEY_PREFIX = "job:"


def job_key(job_id: str) -> str:
    """Build the storage key for a job.

    Args:
        job_id: Unique job identifier.

    Returns:
        The namespaced key used to store the job record.
    """
    return f"{JOB_KEY_PREFIX}{job_id}"


def _merge_fields(record: JobRecord, fields: dict[str, object]) -> JobRecord:
    """Merge non-``None`` fields into a record in place.

    Mirrors the historical update semantics where only explicitly provided
    fields are written (``None`` means "leave unchanged").

    Args:
        record: The record to update.
        fields: Candidate fields; ``None`` values are skipped.

    Returns:
        The same record instance, updated.
    """
    record.update({key: value for key, value in fields.items() if value is not None})
    return record


class JobStore(abc.ABC):
    """Abstract job store shared by the API and the worker."""

    @abc.abstractmethod
    async def create(self, job_id: str, record: JobRecord) -> None:
        """Persist a new job record.

        Args:
            job_id: Unique job identifier.
            record: The full initial job record.
        """

    @abc.abstractmethod
    async def get(self, job_id: str) -> JobRecord | None:
        """Fetch a job record.

        Args:
            job_id: Unique job identifier.

        Returns:
            The job record, or ``None`` if no such job exists.
        """

    @abc.abstractmethod
    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """Merge fields into an existing (or new) job record.

        Only non-``None`` fields are written.

        Args:
            job_id: Unique job identifier.
            **fields: Fields to merge into the record.

        Returns:
            The updated job record.
        """


class InMemoryJobStore(JobStore):
    """Process-local job store backed by a dict.

    Suitable for development, single-process deployments, and tests. Also
    supports a synchronous mapping interface for direct record injection.
    """

    def __init__(self) -> None:
        """Initialize an empty store."""
        self._jobs: dict[str, JobRecord] = {}

    async def create(self, job_id: str, record: JobRecord) -> None:
        """See :meth:`JobStore.create`."""
        self._jobs[job_id] = dict(record)

    async def get(self, job_id: str) -> JobRecord | None:
        """See :meth:`JobStore.get`."""
        return self._jobs.get(job_id)

    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """See :meth:`JobStore.update`."""
        record = self._jobs.setdefault(job_id, {})
        return _merge_fields(record, fields)

    # -- Synchronous mapping helpers (test ergonomics / direct injection) -----

    def __setitem__(self, job_id: str, record: JobRecord) -> None:
        """Inject a record synchronously."""
        self._jobs[job_id] = record

    def __getitem__(self, job_id: str) -> JobRecord:
        """Fetch a record synchronously (raises ``KeyError`` if absent)."""
        return self._jobs[job_id]

    def __contains__(self, job_id: object) -> bool:
        """Return whether a job id is present."""
        return job_id in self._jobs

    def clear(self) -> None:
        """Remove all records."""
        self._jobs.clear()


class RedisJobStore(JobStore):
    """Job store backed by JSON values in Redis.

    Used in production so the API and the separate-process worker share state.
    """

    def __init__(self, redis: Redis, ttl_seconds: int | None = None) -> None:
        """Initialize the Redis-backed store.

        Args:
            redis: An async Redis connection (e.g. the ARQ pool).
            ttl_seconds: Expiry for job records. Defaults to the configured
                ``job_result_ttl_seconds``.
        """
        self._redis = redis
        self._ttl = ttl_seconds or settings.job_result_ttl_seconds

    @staticmethod
    def _decode(raw: object) -> JobRecord | None:
        """Decode a raw Redis value into a record.

        Args:
            raw: Bytes or string fetched from Redis, or ``None``.

        Returns:
            The parsed record, or ``None`` if ``raw`` is ``None``.
        """
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return json.loads(str(raw))

    async def create(self, job_id: str, record: JobRecord) -> None:
        """See :meth:`JobStore.create`."""
        await self._redis.set(job_key(job_id), json.dumps(record), ex=self._ttl)

    async def get(self, job_id: str) -> JobRecord | None:
        """See :meth:`JobStore.get`."""
        raw = await self._redis.get(job_key(job_id))
        return self._decode(raw)

    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """See :meth:`JobStore.update`."""
        record = await self.get(job_id) or {}
        _merge_fields(record, fields)
        await self._redis.set(job_key(job_id), json.dumps(record), ex=self._ttl)
        return record
