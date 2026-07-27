import asyncio
import unittest.mock

import pytest

from src.tts.cache import ExponentialDecayCache


class TestPublicAPI:
    @pytest.fixture
    async def cache(self):
        c = ExponentialDecayCache(capacity=3, half_life_seconds=60.0)
        yield c
        await c.close()

    async def test_put_and_get(self, cache):
        cache.put("a", 1)
        assert cache.get("a") == 1

    async def test_get_missing_returns_none(self, cache):
        assert cache.get("missing") is None

    async def test_put_overwrites_existing(self, cache):
        cache.put("a", 1)
        cache.put("a", 2)
        assert cache.get("a") == 2

    async def test_capacity_zero_does_not_store(self):
        c = ExponentialDecayCache(capacity=0)
        c.put("a", 1)
        assert c.get("a") is None
        assert len(c) == 0
        await c.close()

    async def test_len_empty(self, cache):
        assert len(cache) == 0

    async def test_len_after_put(self, cache):
        cache.put("a", 1)
        assert len(cache) == 1

    async def test_len_after_eviction(self, cache):
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)
        assert len(cache) == 3

    async def test_clear_removes_all_items(self, cache):
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert len(cache) == 0

    async def test_on_evict_called_with_evicted_item(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(capacity=1, half_life_seconds=60.0, on_evict=on_evict)
        c.put("a", 1)
        c.put("b", 2)
        await c.close()
        all_items = []
        for call_args in on_evict.call_args_list:
            batch = call_args[0][0]
            all_items.extend(batch)
        assert ("a", 1) in all_items

    async def test_on_evict_called_with_cleared_items(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(capacity=5, half_life_seconds=60.0, on_evict=on_evict)
        c.put("a", 1)
        c.put("b", 2)
        c.clear()
        await c.close()
        assert on_evict.call_count >= 1
        all_items = []
        for call_args in on_evict.call_args_list:
            batch = call_args[0][0]
            all_items.extend(batch)
        assert ("a", 1) in all_items
        assert ("b", 2) in all_items


class TestScoreEviction:
    async def test_eviction_order_by_score(self):
        capacity = 2
        half_life_seconds = 1

        c = ExponentialDecayCache(capacity=capacity, half_life_seconds=half_life_seconds)
        c.put("a", 1)  # score=1.0 at T0
        await asyncio.sleep(1)  # "a" decays to ~0.5
        c.put("b", 2)  # "b" score=1.0 at T0+1
        c.get("a")  # decays "a" from ~0.5, adds 1.0 → score=~1.5; "b" unchanged
        c.put("c", 3)  # evicts lowest scored: "b" (~1.0) < "a" (~1.5)

        assert c.get("b") is None
        assert c.get("a") == 1
        assert len(c) == 2
        await c.close()


class TestKnownBugs:
    @pytest.fixture
    async def cache(self):
        c = ExponentialDecayCache(capacity=3, half_life_seconds=60.0)
        yield c
        await c.close()

    async def test_no_double_task_done_on_shutdown(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(capacity=1, half_life_seconds=60.0, on_evict=on_evict)
        c.put("a", 1)
        await c.close()
        assert c.is_closed

    async def test_close_terminates_cleaner_task(self, cache):
        cache.put("a", 1)
        await cache.close()
        assert cache.is_closed

    async def test_close_clears_cache(self, cache):
        cache.put("a", 1)
        await cache.close()
        assert len(cache) == 0

    async def test_put_on_closed_cache_raises(self, cache):
        cache.put("a", 1)
        await cache.close()
        with pytest.raises(RuntimeError, match="cache is closed"):
            cache.put("b", 2)
        assert len(cache) == 0

    async def test_none_sentinel_not_passed_to_on_evict(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(capacity=5, half_life_seconds=60.0, on_evict=on_evict)
        c.put("a", 1)
        await c.close()
        for call_args in on_evict.call_args_list:
            batch = call_args[0][0]
            for item in batch:
                assert item is not None

    async def test_close_cancelled_externally_calls_on_evict_emergency(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(
            capacity=5,
            half_life_seconds=60.0,
            eviction_interval=3600.0,
            on_evict=on_evict,
        )
        c.put("k1", "v1")
        c.put("k2", "v2")

        close_task = asyncio.create_task(c.close())
        await asyncio.sleep(0)
        close_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_task

        assert on_evict.call_count >= 1
        all_items = []
        for call_args in on_evict.call_args_list:
            batch = call_args[0][0]
            all_items.extend(batch)
        assert ("k1", "v1") in all_items
        assert ("k2", "v2") in all_items

    async def test_close_cancelled_externally_empty_cache_no_on_evict(self):
        on_evict = unittest.mock.MagicMock()
        c = ExponentialDecayCache(
            capacity=5,
            half_life_seconds=60.0,
            eviction_interval=3600.0,
            on_evict=on_evict,
        )

        close_task = asyncio.create_task(c.close())
        await asyncio.sleep(0)
        close_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_task

        assert on_evict.call_count == 0

    async def test_close_cancelled_externally_on_to_thread_seam(self):
        evicted_items = []

        def on_evict(batch):
            evicted_items.extend(batch)

        c = ExponentialDecayCache(
            capacity=5,
            half_life_seconds=60.0,
            eviction_interval=3600.0,
            on_evict=on_evict,
        )
        c.put("k1", "v1")
        c.put("k2", "v2")

        close_task = asyncio.create_task(c.close())
        await asyncio.sleep(0)
        close_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await close_task

        assert ("k1", "v1") in evicted_items
        assert ("k2", "v2") in evicted_items
