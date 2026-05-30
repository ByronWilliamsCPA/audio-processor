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
from typing import TYPE_CHECKING, cast

from audio_processor.core.config import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable

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
    """Job store backed by a Redis hash per job.

    Used in production so the API and the separate-process worker share state.

    Each job is a Redis hash keyed by ``job:{id}`` whose fields are the record
    keys with individually JSON-encoded values. Partial updates use ``HSET`` on
    only the changed fields, which Redis applies atomically: two writers (e.g.
    the API and the worker) that touch *different* fields no longer clobber each
    other, unlike a whole-record read-modify-write over a single JSON string.
    Concurrent writes to the *same* field remain last-writer-wins, the expected
    contract.

    # #CRITICAL: concurrency: API and worker write the same job from separate
    # processes; field-level HSET is what prevents lost updates.
    # #VERIFY: covered by
    # test_job_store.test_concurrent_field_updates_do_not_clobber.
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
    def _as_text(value: object) -> str:
        """Coerce a Redis hash field/value to ``str`` (clients may not decode).

        Args:
            value: A ``str`` or ``bytes`` returned by ``HGETALL``.

        Returns:
            The value as text.
        """
        return value.decode() if isinstance(value, bytes) else str(value)

    @classmethod
    def _decode_hash(cls, raw: dict[object, object]) -> JobRecord | None:
        """Decode an ``HGETALL`` result into a record.

        Args:
            raw: Mapping of field to JSON-encoded value (possibly ``bytes``).
                An empty mapping means the key is absent.

        Returns:
            The parsed record, or ``None`` if ``raw`` is empty.
        """
        if not raw:
            return None
        return {
            cls._as_text(field): json.loads(cls._as_text(value))
            for field, value in raw.items()
        }

    @staticmethod
    def _encode_fields(fields: dict[str, object]) -> dict[str, str]:
        """JSON-encode each field value for storage as a hash field.

        Args:
            fields: Record fields to encode.

        Returns:
            Mapping of field name to its JSON-encoded value.
        """
        return {field: json.dumps(value) for field, value in fields.items()}

    async def create(self, job_id: str, record: JobRecord) -> None:
        """See :meth:`JobStore.create`."""
        key = job_key(job_id)
        mapping = self._encode_fields(record)
        # Replace any prior record (clears stale fields) and (re)apply the TTL,
        # atomically via MULTI/EXEC.
        pipe = self._redis.pipeline(transaction=True)
        pipe.delete(key)
        if mapping:
            pipe.hset(key, mapping=mapping)
        pipe.expire(key, self._ttl)
        await pipe.execute()

    async def get(self, job_id: str) -> JobRecord | None:
        """See :meth:`JobStore.get`."""
        # redis-py types hash commands as ``Awaitable[...] | ...``; on the async
        # client the value is always awaitable.
        raw = await cast(
            "Awaitable[dict[object, object]]",
            self._redis.hgetall(job_key(job_id)),
        )
        return self._decode_hash(raw)

    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """See :meth:`JobStore.update`.

        Writes only the provided non-``None`` fields with ``HSET`` so concurrent
        writers touching different fields do not overwrite each other.
        """
        key = job_key(job_id)
        mapping = self._encode_fields(
            {name: value for name, value in fields.items() if value is not None}
        )
        if mapping:
            pipe = self._redis.pipeline(transaction=True)
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, self._ttl)
            await pipe.execute()
        return await self.get(job_id) or {}
