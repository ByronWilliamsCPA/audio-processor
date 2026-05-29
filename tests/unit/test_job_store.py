"""Unit tests for the job store abstraction."""

from __future__ import annotations

import json

import pytest

from audio_processor.core.job_store import (
    InMemoryJobStore,
    RedisJobStore,
    job_key,
)


class FakeRedis:
    """Minimal async Redis stand-in supporting get/set with TTL."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.last_ex: int | None = None

    async def get(self, key: str) -> str | None:
        """Return the stored value for ``key`` or ``None``."""
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store ``value`` under ``key`` and record the TTL."""
        self.store[key] = value
        self.last_ex = ex


class TestInMemoryJobStore:
    """Tests for the in-memory job store."""

    @pytest.mark.asyncio
    async def test_create_and_get_roundtrip(self) -> None:
        """A created record should be retrievable by id."""
        store = InMemoryJobStore()
        await store.create("j1", {"status": "queued", "input": {"x": 1}})
        record = await store.get("j1")
        assert record is not None
        assert record["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        """Fetching an unknown job returns None."""
        store = InMemoryJobStore()
        assert await store.get("nope") is None

    @pytest.mark.asyncio
    async def test_update_merges_only_non_none_fields(self) -> None:
        """Update should merge provided fields and skip None values."""
        store = InMemoryJobStore()
        await store.create("j1", {"status": "queued", "error": None})
        await store.update("j1", status="completed", error=None, result={"ok": True})
        record = await store.get("j1")
        assert record is not None
        assert record["status"] == "completed"
        assert record["result"] == {"ok": True}
        # error was None on update -> left unchanged (still None from create)
        assert record["error"] is None

    @pytest.mark.asyncio
    async def test_update_creates_when_absent(self) -> None:
        """Updating an unknown job creates a record."""
        store = InMemoryJobStore()
        await store.update("new", status="failed")
        record = await store.get("new")
        assert record is not None
        assert record["status"] == "failed"

    def test_sync_mapping_interface(self) -> None:
        """The store supports synchronous injection/inspection for tests."""
        store = InMemoryJobStore()
        store["j1"] = {"status": "queued"}
        assert "j1" in store
        assert store["j1"]["status"] == "queued"
        store.clear()
        assert "j1" not in store

    @pytest.mark.asyncio
    async def test_injected_record_visible_to_async_get(self) -> None:
        """A synchronously injected record is visible via async get."""
        store = InMemoryJobStore()
        store["j1"] = {"status": "completed"}
        record = await store.get("j1")
        assert record is not None
        assert record["status"] == "completed"


class TestRedisJobStore:
    """Tests for the Redis-backed job store using a fake connection."""

    @pytest.mark.asyncio
    async def test_create_serializes_json_with_ttl(self) -> None:
        """Create should write JSON under the namespaced key with a TTL."""
        redis = FakeRedis()
        store = RedisJobStore(redis, ttl_seconds=123)  # type: ignore[arg-type]
        await store.create("j1", {"status": "queued"})
        assert json.loads(redis.store[job_key("j1")]) == {"status": "queued"}
        assert redis.last_ex == 123

    @pytest.mark.asyncio
    async def test_get_decodes_bytes_and_str(self) -> None:
        """Get should decode both bytes and str Redis payloads."""
        redis = FakeRedis()
        store = RedisJobStore(redis)  # type: ignore[arg-type]
        redis.store[job_key("b")] = json.dumps({"status": "a"})
        assert await store.get("b") == {"status": "a"}
        # Cover the bytes-decode branch as well.
        redis.store[job_key("c")] = json.dumps({"status": "z"}).encode()
        assert await store.get("c") == {"status": "z"}

    @pytest.mark.asyncio
    async def test_update_merges_existing_record(self) -> None:
        """Update should merge into the existing stored record."""
        redis = FakeRedis()
        store = RedisJobStore(redis)  # type: ignore[arg-type]
        await store.create("j1", {"status": "queued", "progress": None})
        await store.update("j1", status="transcribing", progress={"pct": 50})
        record = await store.get("j1")
        assert record == {"status": "transcribing", "progress": {"pct": 50}}

    @pytest.mark.asyncio
    async def test_update_on_missing_creates_record(self) -> None:
        """Update on an absent key starts from an empty record."""
        redis = FakeRedis()
        store = RedisJobStore(redis)  # type: ignore[arg-type]
        await store.update("missing", status="failed")
        assert await store.get("missing") == {"status": "failed"}
