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
import copy
import json
from typing import TYPE_CHECKING, cast

from audio_processor.core.config import settings
from audio_processor.core.exceptions import ConfigurationError, DatabaseError
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from redis.asyncio import Redis

logger = get_logger(__name__)

# A job record is a JSON-serializable mapping. Values are intentionally broad
# (object) because records carry mixed content (status strings, nested input
# dicts, progress dicts, results, ISO timestamps).
JobRecord = dict[str, object]

JOB_KEY_PREFIX = "job:"


def job_key(job_id: str) -> str:
    """Build the storage key for a job.

    Args:
        job_id (str): Unique job identifier.

    Returns:
        str: The namespaced key used to store the job record.
    """
    return f"{JOB_KEY_PREFIX}{job_id}"


def _merge_fields(record: JobRecord, fields: dict[str, object]) -> JobRecord:
    """Merge non-``None`` fields into a record in place.

    Mirrors the historical update semantics where only explicitly provided
    fields are written (``None`` means "leave unchanged").

    Args:
        record (JobRecord): The record to update.
        fields (dict[str, object]): Candidate fields; ``None`` values are skipped.

    Returns:
        JobRecord: The same record instance, updated.
    """
    record.update({key: value for key, value in fields.items() if value is not None})
    return record


class JobStore(abc.ABC):
    """Abstract job store shared by the API and the worker."""

    @abc.abstractmethod
    async def create(self, job_id: str, record: JobRecord) -> None:
        """Persist a new job record.

        Args:
            job_id (str): Unique job identifier.
            record (JobRecord): The full initial job record.
        """

    @abc.abstractmethod
    async def get(self, job_id: str) -> JobRecord | None:
        """Fetch a job record.

        Args:
            job_id (str): Unique job identifier.

        Returns:
            JobRecord | None: The job record, or ``None`` if no such job exists.
        """

    @abc.abstractmethod
    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """Merge fields into an existing (or new) job record.

        Only non-``None`` fields are written.

        Args:
            job_id (str): Unique job identifier.
            **fields (object): Fields to merge into the record.

        Returns:
            JobRecord: The updated job record.
        """


class InMemoryJobStore(JobStore):
    """Process-local job store backed by a dict.

    Suitable for development, single-process deployments, and tests. Also
    supports a synchronous mapping interface for direct record injection.
    Initializes with an empty job store.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    async def create(self, job_id: str, record: JobRecord) -> None:
        """See :meth:`JobStore.create`."""
        # Deep-copy on store so later mutation of the caller's input (including
        # nested dicts) cannot reach stored state, matching RedisJobStore, which
        # round-trips every value through JSON.
        self._jobs[job_id] = copy.deepcopy(record)

    async def get(self, job_id: str) -> JobRecord | None:
        """See :meth:`JobStore.get`."""
        # Deep-copy so callers cannot mutate stored state out of band, including
        # nested values (progress/input/result dicts). A shallow ``dict`` copy
        # would leave those aliased; RedisJobStore returns freshly decoded
        # objects, and this keeps the in-memory backend faithful to that.
        record = self._jobs.get(job_id)
        return copy.deepcopy(record) if record is not None else None

    async def update(self, job_id: str, **fields: object) -> JobRecord:
        """See :meth:`JobStore.update`."""
        record = self._jobs.setdefault(job_id, {})
        # Deep-copy incoming values before merging so a caller mutating a
        # passed-in nested object later cannot reach stored state, and deep-copy
        # the result so the returned record is likewise isolated.
        _merge_fields(record, copy.deepcopy(fields))
        return copy.deepcopy(record)

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

    Args:
        redis (Redis): An async Redis connection (e.g. the ARQ pool).
        ttl_seconds (int | None): Expiry for job records. Defaults to the configured
            ``job_result_ttl_seconds``.

    Raises:
        ConfigurationError: If the resolved TTL is not a positive number of
            seconds. A non-positive TTL reaching Redis ``EXPIRE`` deletes the
            key immediately, so newly written jobs would silently vanish; this
            surfaces the misconfiguration loudly instead.
    """

    def __init__(self, redis: Redis, ttl_seconds: int | None = None) -> None:
        self._redis = redis
        # Use ``is not None`` so an explicit 0/negative is not silently coerced
        # to the default; reject it instead. A non-positive TTL reaching Redis
        # EXPIRE deletes the key at once, which would make new jobs disappear.
        resolved_ttl = (
            ttl_seconds if ttl_seconds is not None else settings.job_result_ttl_seconds
        )
        if resolved_ttl <= 0:
            msg = f"job result TTL must be positive seconds, got {resolved_ttl}"
            raise ConfigurationError(msg)
        self._ttl = resolved_ttl

    @staticmethod
    def _as_text(value: object) -> str:
        """Coerce a Redis hash field/value to ``str`` (clients may not decode).

        Args:
            value (object): A ``str`` or ``bytes`` returned by ``HGETALL``.

        Returns:
            str: The value as text.
        """
        return value.decode() if isinstance(value, bytes) else str(value)

    @classmethod
    def _decode_hash(cls, raw: dict[object, object]) -> JobRecord | None:
        """Decode an ``HGETALL`` result into a record.

        Args:
            raw (dict[object, object]): Mapping of field to JSON-encoded value (possibly ``bytes``).
                An empty mapping means the key is absent.

        Returns:
            JobRecord | None: The parsed record, or ``None`` if ``raw`` is empty.

        Raises:
            DatabaseError: If a stored field value is not valid JSON (a corrupt
                or legacy record); surfaced as a typed, logged error rather than
                letting a raw ``JSONDecodeError`` crash the caller.
        """
        if not raw:
            return None
        try:
            return {
                cls._as_text(field): json.loads(cls._as_text(value))
                for field, value in raw.items()
            }
        except ValueError as exc:
            # ``json.JSONDecodeError`` is a ``ValueError`` subclass, so catching
            # ``ValueError`` alone covers a non-JSON (corrupt/legacy) field value.
            logger.exception("job_record_decode_failed")
            msg = "Corrupted job record in store"
            raise DatabaseError(msg, operation="decode") from exc

    @staticmethod
    def _encode_fields(fields: dict[str, object]) -> dict[str, str]:
        """JSON-encode each field value for storage as a hash field.

        Args:
            fields (dict[str, object]): Record fields to encode.

        Returns:
            dict[str, str]: Mapping of field name to its JSON-encoded value.
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
