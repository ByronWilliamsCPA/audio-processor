"""Tests for Redis caching utilities."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import RedisError

from audio_processor.core.cache import (
    cache_invalidate,
    cached,
    close_redis,
    delete_cached,
    get_cache_stats,
    get_cached,
    get_redis,
    invalidate_pattern,
    set_cached,
    warm_cache,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock()
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.exists = AsyncMock()
    redis_mock.info = AsyncMock()
    redis_mock.close = AsyncMock()

    # scan_iter needs to be a regular Mock that returns an async iterator
    def scan_iter_factory(items):
        async def async_gen():
            for item in items:
                yield item

        return async_gen()

    redis_mock.scan_iter = MagicMock(side_effect=lambda **kwargs: scan_iter_factory([]))
    return redis_mock


@pytest.fixture(autouse=True)
def reset_redis_pool():
    """Reset the global Redis pool before each test."""
    # Import the module to access global variable
    from audio_processor.core import cache

    cache._redis_pool = None
    yield
    cache._redis_pool = None


class TestGetRedis:
    """Tests for get_redis connection management."""

    @pytest.mark.asyncio
    async def test_get_redis_initializes_pool(self, mock_redis: AsyncMock) -> None:
        """Test that get_redis initializes connection pool on first call."""
        with patch("audio_processor.core.cache.from_url", return_value=mock_redis):
            redis = await get_redis()
            assert redis is not None
            assert redis == mock_redis

    @pytest.mark.asyncio
    async def test_get_redis_reuses_pool(self, mock_redis: AsyncMock) -> None:
        """Test that get_redis reuses existing pool."""
        with patch("audio_processor.core.cache.from_url", return_value=mock_redis):
            redis1 = await get_redis()
            redis2 = await get_redis()
            assert redis1 is redis2

    @pytest.mark.asyncio
    async def test_get_redis_uses_env_url(self, mock_redis: AsyncMock) -> None:
        """Test that get_redis uses REDIS_URL from environment."""
        test_url = "redis://testhost:6380/1"
        with (
            patch(
                "audio_processor.core.cache.from_url", return_value=mock_redis
            ) as mock_from_url,
            patch.dict("os.environ", {"REDIS_URL": test_url}),
        ):
            await get_redis()
            mock_from_url.assert_called_once()
            call_args = mock_from_url.call_args
            assert call_args[0][0] == test_url

    @pytest.mark.asyncio
    async def test_get_redis_default_url(self, mock_redis: AsyncMock) -> None:
        """Test that get_redis uses default URL when env var not set."""
        with (
            patch(
                "audio_processor.core.cache.from_url", return_value=mock_redis
            ) as mock_from_url,
            patch.dict("os.environ", {}, clear=True),
        ):
            await get_redis()
            mock_from_url.assert_called_once()
            call_args = mock_from_url.call_args
            assert call_args[0][0] == "redis://localhost:6379/0"


class TestCloseRedis:
    """Tests for close_redis connection cleanup."""

    @pytest.mark.asyncio
    async def test_close_redis_closes_pool(self, mock_redis: AsyncMock) -> None:
        """Test that close_redis closes the connection pool."""
        with patch("audio_processor.core.cache.from_url", return_value=mock_redis):
            await get_redis()
            await close_redis()
            mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_redis_when_pool_none(self) -> None:
        """Test that close_redis handles None pool gracefully."""
        # Should not raise an error
        await close_redis()


class TestCachedDecorator:
    """Tests for @cached decorator."""

    @pytest.mark.asyncio
    async def test_cached_cache_miss(self, mock_redis: AsyncMock) -> None:
        """Test cached decorator on cache miss."""
        mock_redis.get.return_value = None

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):

            @cached(ttl=300)
            async def test_func(value: int) -> dict:
                return {"result": value * 2}

            result = await test_func(5)

            assert result == {"result": 10}
            mock_redis.get.assert_called_once()
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_cache_hit(self, mock_redis: AsyncMock) -> None:
        """Test cached decorator on cache hit."""
        cached_value = {"result": 100}
        mock_redis.get.return_value = json.dumps(cached_value)

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            call_count = 0

            @cached(ttl=300)
            async def test_func(value: int) -> dict:
                nonlocal call_count
                call_count += 1
                return {"result": value * 2}

            result = await test_func(50)

            # Should return cached value without calling function
            assert result == cached_value
            assert call_count == 0
            mock_redis.get.assert_called_once()
            mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_cached_custom_key_prefix(self, mock_redis: AsyncMock) -> None:
        """Test cached decorator with custom key prefix."""
        mock_redis.get.return_value = None

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):

            @cached(ttl=300, key_prefix="custom")
            async def test_func(value: int) -> dict:
                return {"result": value}

            await test_func(5)

            # Check that key starts with custom prefix
            call_args = mock_redis.setex.call_args
            assert call_args[0][0].startswith("custom:")

    @pytest.mark.asyncio
    async def test_cached_custom_key_builder(self, mock_redis: AsyncMock) -> None:
        """Test cached decorator with custom key builder."""
        mock_redis.get.return_value = None

        def custom_builder(value: int) -> str:
            return f"mykey:{value}"

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):

            @cached(ttl=300, key_builder=custom_builder)
            async def test_func(value: int) -> dict:
                return {"result": value}

            await test_func(42)

            # Check that custom key was used
            call_args = mock_redis.get.call_args
            assert call_args[0][0] == "mykey:42"

    @pytest.mark.asyncio
    async def test_cached_redis_error_fallback(self, mock_redis: AsyncMock) -> None:
        """Test cached decorator falls back gracefully on Redis error."""
        mock_redis.get.side_effect = RedisError("Connection failed")

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.warning"),
        ):

            @cached(ttl=300)
            async def test_func(value: int) -> dict:
                return {"result": value * 2}

            # Should still work by calling function directly
            result = await test_func(5)
            assert result == {"result": 10}

    @pytest.mark.asyncio
    async def test_cached_ttl_passed_to_redis(self, mock_redis: AsyncMock) -> None:
        """Test that TTL is correctly passed to Redis."""
        mock_redis.get.return_value = None
        custom_ttl = 7200

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):

            @cached(ttl=custom_ttl)
            async def test_func(value: int) -> dict:
                return {"result": value}

            await test_func(5)

            # Check TTL argument
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == custom_ttl


class TestCacheInvalidateDecorator:
    """Tests for @cache_invalidate decorator."""

    @pytest.mark.asyncio
    async def test_cache_invalidate_success(self, mock_redis: AsyncMock) -> None:
        """Test cache_invalidate decorator successfully invalidates cache."""

        async def scan_iter_mock(**kwargs):
            for key in ["key1", "key2"]:
                yield key

        mock_redis.scan_iter = MagicMock(return_value=scan_iter_mock())
        mock_redis.delete.return_value = 2

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):

            @cache_invalidate("user:*")
            async def update_user(user_id: str) -> dict:
                return {"updated": user_id}

            result = await update_user("123")

            assert result == {"updated": "123"}
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_invalidate_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test cache_invalidate handles Redis errors gracefully."""

        async def scan_iter_error(**kwargs):
            raise RedisError("Connection failed")
            yield

        mock_redis.scan_iter = MagicMock(return_value=scan_iter_error())

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.warning"),
            patch("audio_processor.core.cache.logger.exception"),
        ):

            @cache_invalidate("user:*")
            async def update_user(user_id: str) -> dict:
                return {"updated": user_id}

            # Should still return result even if invalidation fails
            result = await update_user("123")
            assert result == {"updated": "123"}


class TestGetCached:
    """Tests for get_cached function."""

    @pytest.mark.asyncio
    async def test_get_cached_key_exists(self, mock_redis: AsyncMock) -> None:
        """Test get_cached when key exists."""
        test_value = {"data": "test"}
        mock_redis.get.return_value = json.dumps(test_value)

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await get_cached("test_key")
            assert result == test_value

    @pytest.mark.asyncio
    async def test_get_cached_key_not_exists(self, mock_redis: AsyncMock) -> None:
        """Test get_cached when key doesn't exist."""
        mock_redis.get.return_value = None

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await get_cached("test_key")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_default_value(self, mock_redis: AsyncMock) -> None:
        """Test get_cached returns default when key not found."""
        mock_redis.get.return_value = None
        default = {"default": "value"}

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await get_cached("test_key", default=default)
            assert result == default

    @pytest.mark.asyncio
    async def test_get_cached_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test get_cached handles Redis errors."""
        mock_redis.get.side_effect = RedisError("Connection failed")
        default = {"default": "value"}

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.warning"),
        ):
            result = await get_cached("test_key", default=default)
            assert result == default


class TestSetCached:
    """Tests for set_cached function."""

    @pytest.mark.asyncio
    async def test_set_cached_success(self, mock_redis: AsyncMock) -> None:
        """Test set_cached successfully stores value."""
        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await set_cached("test_key", {"data": "test"}, ttl=300)

            assert result is True
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert call_args[0][0] == "test_key"
            assert call_args[0][1] == 300

    @pytest.mark.asyncio
    async def test_set_cached_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test set_cached handles Redis errors."""
        mock_redis.setex.side_effect = RedisError("Connection failed")

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.warning"),
        ):
            result = await set_cached("test_key", {"data": "test"})
            assert result is False


class TestDeleteCached:
    """Tests for delete_cached function."""

    @pytest.mark.asyncio
    async def test_delete_cached_key_exists(self, mock_redis: AsyncMock) -> None:
        """Test delete_cached when key exists."""
        mock_redis.delete.return_value = 1

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await delete_cached("test_key")
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_cached_key_not_exists(self, mock_redis: AsyncMock) -> None:
        """Test delete_cached when key doesn't exist."""
        mock_redis.delete.return_value = 0

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await delete_cached("test_key")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_cached_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test delete_cached handles Redis errors."""
        mock_redis.delete.side_effect = RedisError("Connection failed")

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.warning"),
        ):
            result = await delete_cached("test_key")
            assert result is False


class TestInvalidatePattern:
    """Tests for invalidate_pattern function."""

    @pytest.mark.asyncio
    async def test_invalidate_pattern_with_matches(self, mock_redis: AsyncMock) -> None:
        """Test invalidate_pattern deletes matching keys."""

        async def scan_iter_mock(**kwargs):
            for key in ["user:1", "user:2", "user:3"]:
                yield key

        mock_redis.scan_iter = MagicMock(return_value=scan_iter_mock())
        mock_redis.delete.return_value = 3

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            count = await invalidate_pattern("user:*")

            assert count == 3
            mock_redis.delete.assert_called_once_with("user:1", "user:2", "user:3")

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_matches(self, mock_redis: AsyncMock) -> None:
        """Test invalidate_pattern when no keys match."""

        async def scan_iter_mock(**kwargs):
            return
            yield

        mock_redis.scan_iter = MagicMock(return_value=scan_iter_mock())

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            count = await invalidate_pattern("nonexistent:*")

            assert count == 0
            mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_pattern_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test invalidate_pattern handles Redis errors."""

        async def scan_iter_error(**kwargs):
            raise RedisError("Connection failed")
            yield

        mock_redis.scan_iter = MagicMock(return_value=scan_iter_error())

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.exception"),
        ):
            count = await invalidate_pattern("user:*")
            assert count == 0


class TestWarmCache:
    """Tests for warm_cache function."""

    @pytest.mark.asyncio
    async def test_warm_cache_new_key(self, mock_redis: AsyncMock) -> None:
        """Test warm_cache with new key."""
        mock_redis.exists.return_value = 0

        async def value_fn() -> dict:
            return {"data": "test"}

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await warm_cache("test_key", value_fn, ttl=3600)

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_existing_key_no_force(
        self, mock_redis: AsyncMock
    ) -> None:
        """Test warm_cache with existing key and no force."""
        mock_redis.exists.return_value = 1

        async def value_fn() -> dict:
            return {"data": "test"}

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await warm_cache("test_key", value_fn, ttl=3600, force=False)

            assert result is False
            mock_redis.setex.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_cache_existing_key_with_force(
        self, mock_redis: AsyncMock
    ) -> None:
        """Test warm_cache with existing key and force=True."""
        mock_redis.exists.return_value = 1

        async def value_fn() -> dict:
            return {"data": "refreshed"}

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            result = await warm_cache("test_key", value_fn, ttl=3600, force=True)

            assert result is True
            mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_cache_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test warm_cache handles Redis errors."""
        mock_redis.exists.side_effect = RedisError("Connection failed")

        async def value_fn() -> dict:
            return {"data": "test"}

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.exception"),
        ):
            result = await warm_cache("test_key", value_fn)
            assert result is False


class TestGetCacheStats:
    """Tests for get_cache_stats function."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self, mock_redis: AsyncMock) -> None:
        """Test get_cache_stats returns statistics."""
        mock_redis.info.return_value = {
            "keyspace_hits": 1000,
            "keyspace_misses": 200,
            "used_memory_human": "1.5M",
            "connected_clients": 5,
        }

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            stats = await get_cache_stats()

            assert stats["hits"] == 1000
            assert stats["misses"] == 200
            assert stats["hit_rate"] == pytest.approx(83.33, rel=0.01)
            assert stats["memory_used"] == "1.5M"
            assert stats["connected_clients"] == 5

    @pytest.mark.asyncio
    async def test_get_cache_stats_zero_hits_misses(
        self, mock_redis: AsyncMock
    ) -> None:
        """Test get_cache_stats with zero hits and misses."""
        mock_redis.info.return_value = {
            "keyspace_hits": 0,
            "keyspace_misses": 0,
        }

        with patch("audio_processor.core.cache.get_redis", return_value=mock_redis):
            stats = await get_cache_stats()

            # Should handle division by zero
            assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_get_cache_stats_redis_error(self, mock_redis: AsyncMock) -> None:
        """Test get_cache_stats handles Redis errors."""
        mock_redis.info.side_effect = RedisError("Connection failed")

        with (
            patch("audio_processor.core.cache.get_redis", return_value=mock_redis),
            patch("audio_processor.core.cache.logger.exception"),
        ):
            stats = await get_cache_stats()
            assert "error" in stats
