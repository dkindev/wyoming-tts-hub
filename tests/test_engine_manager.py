import asyncio

import pytest

from src.tts.engine_manager import CLEANER_INTERVAL_SECONDS, TtsEngineManager
from src.tts.models import BackendType, TextFormat
from tests.helpers import (
    FakeDataStorage,
    FakeEngineFactory,
    FakeTtsEngine,
    make_model,
    make_voice,
)

MODEL_ID = "v5_5_ru"
VOICE_ID = "v5_5_ru-aidar"

# A test that waits for the background cleaner to drain an engine must allow more
# than one poll of its interval.
CLEANER_TIMEOUT_SECONDS = CLEANER_INTERVAL_SECONDS * 4


async def wait_until(predicate, timeout=CLEANER_TIMEOUT_SECONDS, interval=0.05):
    """Await `predicate()` becoming true, polling until `timeout` elapses."""
    deadline = asyncio.get_running_loop().time() + timeout

    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)

    return predicate()


async def wait_for_cleaner_cycle():
    """Sleep past one background-cleaner poll, so deferred work would have run."""
    await asyncio.sleep(CLEANER_INTERVAL_SECONDS + 0.5)


def make_manager(
    *,
    models=(),
    engines=None,
    cache_capacity=2,
    max_concurrent_sentences_per_model=1,
    half_life_seconds=600.0,
    inference_timeout=5.0,
):
    """Return a manager wired to fakes, plus the factory and storage behind it."""
    models = list(models) or [make_model(id=MODEL_ID, warmup=False)]
    factory = FakeEngineFactory(engines=engines)
    storage = FakeDataStorage(models=models)

    manager = TtsEngineManager(
        backendType=BackendType.TORCH,
        cache_half_life_seconds=half_life_seconds,
        cache_capacity=cache_capacity,
        inference_timeout=inference_timeout,
        max_concurrent_sentences_per_model=max_concurrent_sentences_per_model,
        engine_factory=factory,
        data_storage=storage,
    )
    return manager, factory, storage


def make_engine(model_id=MODEL_ID, **kwargs):
    """Return a FakeTtsEngine for `model_id`, with the default Voice pointing at it."""
    return FakeTtsEngine(make_model(id=model_id), **kwargs)


def make_voice_for(model_id=MODEL_ID):
    return make_voice(voice_id=VOICE_ID, name="aidar", model=model_id)


async def synthesize_via(manager, model_id=MODEL_ID, text="hello"):
    """Run one synthesis through `manager` for `model_id`, consuming all chunks."""
    voice = make_voice_for(model_id)
    async with await manager.get_context(model_id) as engine:
        return await _drain(engine.synthesize_pcm(text, voice, TextFormat.TEXT))


class TestWarmup:
    async def test_warmup_loads_only_models_flagged_for_warmup(self):
        """Only Models flagged `warmup` are loaded at startup."""
        eager = make_model(id="eager", warmup=True)
        lazy = make_model(id="lazy", warmup=False)
        eager_engine = make_engine("eager")
        lazy_engine = make_engine("lazy")
        manager, factory, _ = make_manager(
            models=[eager, lazy],
            engines={"eager": eager_engine, "lazy": lazy_engine},
        )

        await manager.warmup()
        await manager.close()

        assert eager_engine.warmup_count == 1
        assert lazy_engine.warmup_count == 0

    async def test_model_failing_warmup_is_skipped_and_others_still_load(self):
        """A Model that raises during warmup is skipped; the rest still load."""
        broken = make_model(id="broken", warmup=True)
        healthy = make_model(id="healthy", warmup=True)
        healthy_engine = make_engine("healthy")
        manager, _, _ = make_manager(
            models=[broken, healthy],
            engines={
                "broken": make_engine("broken", warmup_error=RuntimeError("no such model")),
                "healthy": healthy_engine,
            },
        )

        await manager.warmup()
        await manager.close()

        assert healthy_engine.warmup_count == 1

    async def test_warmup_does_nothing_when_models_already_loaded(self):
        """Warmup is a no-op once the manager holds engines."""
        engine = make_engine()
        manager, _, _ = make_manager(
            models=[make_model(id=MODEL_ID, warmup=True)], engines={MODEL_ID: engine}
        )

        await manager.warmup()
        await manager.warmup()
        await manager.close()

        assert engine.warmup_count == 1


class TestOnDemandLoading:
    async def test_first_request_loads_engine_and_second_reuses_it(self):
        """A Model is loaded once on first use, and later requests reuse that engine."""
        engine = make_engine()
        manager, factory, _ = make_manager(engines={MODEL_ID: engine})

        first = await synthesize_via(manager)
        second = await synthesize_via(manager)
        await manager.close()

        assert engine.warmup_count == 1
        assert factory.requested_model_ids == [MODEL_ID]
        assert len(first) > 0
        assert len(second) > 0

    async def test_request_for_unknown_model_raises(self):
        """Asking for a Model the storage does not know raises an error naming it."""
        manager, _, _ = make_manager()

        with pytest.raises(RuntimeError) as exc_info:
            await synthesize_via(manager, model_id="no_such_model")
        await manager.close()

        assert "no_such_model" in str(exc_info.value)


class TestConcurrency:
    async def test_no_more_than_the_configured_sentences_synthesize_at_once(self):
        """With the per-Model limit at two, a third sentence waits rather than proceeding."""
        release = asyncio.Event()
        engine = make_engine(hold=release)
        manager, _, _ = make_manager(
            engines={MODEL_ID: engine}, max_concurrent_sentences_per_model=2
        )

        started = [asyncio.create_task(synthesize_via(manager)) for _ in range(3)]

        # Let the first two acquire the semaphore and block inside synthesis.
        assert await wait_until(lambda: engine.active_syntheses == 2, timeout=5.0)
        assert engine.peak_syntheses == 2

        release.set()
        await asyncio.gather(*started)
        await manager.close()

        assert engine.peak_syntheses == 2


class TestEviction:
    async def test_evicted_model_engine_is_closed_exactly_once(self):
        """Evicting the least-recently-used Model closes its engine once."""
        evicted = make_engine("evicted")
        kept = make_engine("kept")
        manager, _, _ = make_manager(
            models=[make_model(id="evicted"), make_model(id="kept")],
            engines={"evicted": evicted, "kept": kept},
            cache_capacity=1,
        )

        await synthesize_via(manager, model_id="evicted")
        await synthesize_via(manager, model_id="kept")

        assert await wait_until(lambda: evicted.close_count == 1)
        await manager.close()

        assert evicted.close_count == 1

    async def test_least_recently_used_model_is_the_one_evicted(self):
        """The recently-used Model survives eviction; the idle one is closed."""
        idle = make_engine("idle")
        recent = make_engine("recent")
        newcomer = make_engine("newcomer")
        manager, _, _ = make_manager(
            models=[make_model(id="idle"), make_model(id="recent"), make_model(id="newcomer")],
            engines={"idle": idle, "recent": recent, "newcomer": newcomer},
            cache_capacity=2,
        )

        await synthesize_via(manager, model_id="idle")
        await synthesize_via(manager, model_id="recent")
        # Touch "idle" so "recent" becomes the least recently used.
        await synthesize_via(manager, model_id="idle")
        await synthesize_via(manager, model_id="newcomer")

        assert await wait_until(lambda: recent.close_count == 1)

        # Before shutdown, only the least recently used Model has been torn down.
        assert idle.close_count == 0
        assert recent.close_count == 1

        await manager.close()

        assert idle.close_count == 1

    async def test_model_in_use_is_closed_only_after_its_request_completes(self):
        """A Model held by an in-flight request is deferred, then closed once released."""
        release = asyncio.Event()
        held = make_engine("held", hold=release)
        manager, _, _ = make_manager(
            models=[make_model(id="held"), make_model(id="other")],
            engines={"held": held},
            cache_capacity=1,
        )

        voice = make_voice_for("held")
        async with await manager.get_context("held") as shared:
            request = asyncio.create_task(
                _drain(shared.synthesize_pcm("hello", voice, TextFormat.TEXT))
            )
            assert await wait_until(lambda: held.active_syntheses == 1, timeout=5.0)

            # Loading a second Model evicts "held", but the in-flight request still holds it.
            await synthesize_via(manager, model_id="other")

            # Wait past a background-cleaner poll: eviction must be deferred, not merely
            # pending, so "held" has to survive a full cleaner cycle while still in use.
            await wait_for_cleaner_cycle()
            assert held.close_count == 0

            release.set()
            await request

        assert await wait_until(lambda: held.close_count == 1)
        await manager.close()

        assert held.close_count == 1


class TestCancelledAcquire:
    """A cancelled acquire must leave the Model as free as it was before the request.

    Lands a failing test on purpose (ticket 08): it documents a defect rather than
    fixing it. The Engine Context takes the Model's reference before awaiting the
    per-Model concurrency limit, so a caller cancelled during that wait leaves the
    reference behind for good — the Model then looks permanently in use, eviction
    is deferred forever, and the engine is never closed.
    """

    async def test_cancelled_acquire_leaves_the_model_evictable(self):
        """Cancelling a request blocked on the per-Model limit does not pin the Model."""
        release = asyncio.Event()
        evictable = make_engine("evictable", hold=release)
        manager, _, _ = make_manager(
            models=[make_model(id="evictable"), make_model(id="other")],
            engines={"evictable": evictable},
            cache_capacity=1,
            max_concurrent_sentences_per_model=1,
        )
        voice = make_voice_for("evictable")

        async with await manager.get_context("evictable") as shared:
            held = asyncio.create_task(
                _drain(shared.synthesize_pcm("hello", voice, TextFormat.TEXT))
            )
            assert await wait_until(lambda: evictable.active_syntheses == 1, timeout=5.0)

            # A second request for the same Model waits for the concurrency limit.
            # The Model is cached and the limit is taken, so the only await left on
            # this path is the semaphore: yielding a few times puts the task there.
            waiting = asyncio.create_task(synthesize_via(manager, model_id="evictable"))
            for _ in range(3):
                await asyncio.sleep(0)
            assert not waiting.done()
            assert evictable.peak_syntheses == 1, "the second request must not have started"

            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting

            release.set()
            await held

        # Loading another Model evicts "evictable". A cancelled acquire must not be
        # holding it, so the background cleaner closes the engine as usual.
        await synthesize_via(manager, model_id="other")
        await wait_for_cleaner_cycle()

        assert evictable.close_count == 1
        await manager.close()

        assert evictable.close_count == 1, "shutdown must not close an already-closed engine"


class TestShutdown:
    async def test_shutdown_closes_every_remaining_engine_exactly_once(self):
        """Shutting down closes each engine the manager still holds, once."""
        first = make_engine("first")
        second = make_engine("second")
        manager, _, _ = make_manager(
            models=[make_model(id="first"), make_model(id="second")],
            engines={"first": first, "second": second},
        )

        await synthesize_via(manager, model_id="first")
        await synthesize_via(manager, model_id="second")
        await manager.close()

        assert first.close_count == 1
        assert second.close_count == 1

    async def test_shutdown_closes_engines_deferred_from_eviction(self):
        """Shutdown drains engines still in use, closing each exactly once."""
        release = asyncio.Event()
        held = make_engine("held", hold=release)
        manager, _, _ = make_manager(
            models=[make_model(id="held"), make_model(id="other")],
            engines={"held": held},
            cache_capacity=1,
        )

        voice = make_voice_for("held")
        async with await manager.get_context("held") as shared:
            request = asyncio.create_task(
                _drain(shared.synthesize_pcm("hello", voice, TextFormat.TEXT))
            )
            assert await wait_until(lambda: held.active_syntheses == 1, timeout=5.0)

            # Evict "held" while it is in use, then shut down before the request finishes.
            await synthesize_via(manager, model_id="other")
            await manager.close()

            release.set()
            await request

        assert held.close_count == 1

    async def test_shutdown_is_safe_to_call_twice(self):
        """Calling close() twice is harmless and does not re-close engines."""
        engine = make_engine()
        manager, _, _ = make_manager(engines={MODEL_ID: engine})

        await synthesize_via(manager)
        await manager.close()
        await manager.close()

        assert engine.close_count == 1

    async def test_requesting_a_model_after_shutdown_raises(self):
        """Using the manager after shutdown is an error."""
        manager, _, _ = make_manager()

        await manager.close()

        with pytest.raises(RuntimeError) as exc_info:
            await synthesize_via(manager)

        assert "closed" in str(exc_info.value).lower()


async def _drain(stream):
    return [chunk async for chunk in stream]
