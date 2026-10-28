import asyncio

import pytest

from src.tts.engine_manager import CLEANER_INTERVAL_SECONDS, TtsEngineManager
from src.tts.models import BackendType, TextFormat
from tests.helpers import (
    FakeDataStorage,
    FakeEngineFactory,
    FakeTtsEngine,
    make_model_info,
    make_voice,
)

MODEL_ID = "v5_6_ru"
VOICE_ID = "v5_6_ru-aidar"

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
    voices=(),
    engines=None,
    cache_capacity=2,
    max_concurrent_sentences_per_model=1,
    max_voice_prompts=8,
    half_life_seconds=600.0,
    inference_timeout=5.0,
):
    """Return a manager wired to fakes, plus the factory and storage behind it."""
    models = list(models) or [make_model_info(id=MODEL_ID, warmup=False)]
    factory = FakeEngineFactory(engines=engines)
    storage = FakeDataStorage(models=models, voices=list(voices))

    manager = TtsEngineManager(
        backendType=BackendType.TORCH,
        cache_half_life_seconds=half_life_seconds,
        cache_capacity=cache_capacity,
        inference_timeout=inference_timeout,
        max_concurrent_sentences_per_model=max_concurrent_sentences_per_model,
        max_voice_prompts=max_voice_prompts,
        engine_factory=factory,
        data_storage=storage,
    )
    return manager, factory, storage


def make_engine(model_id=MODEL_ID, **kwargs):
    """Return a FakeTtsEngine for `model_id`, with the default Voice pointing at it."""
    return FakeTtsEngine(make_model_info(id=model_id), **kwargs)


def make_voice_for(model_id=MODEL_ID):
    return make_voice(voice_id=VOICE_ID, name="aidar", model=model_id)


async def synthesize_via(manager, model_id=MODEL_ID, text="hello"):
    """Run one synthesis through `manager` for `model_id`, consuming all chunks."""
    voice = make_voice_for(model_id)
    async with await manager.get_context(model_id) as engine:
        return await _drain(engine.synthesize_pcm(text, voice, TextFormat.TEXT))


class TestWarmup:
    async def test_warmup_loads_only_models_flagged_for_warmup(self):
        """Only Model Infos flagged `warmup` are loaded at startup."""
        eager = make_model_info(id="eager", warmup=True)
        lazy = make_model_info(id="lazy", warmup=False)
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

    async def test_model_info_failing_warmup_is_skipped_and_others_still_load(self):
        """A Model Info whose engine raises during warmup is skipped; the rest still load."""
        broken = make_model_info(id="broken", warmup=True)
        healthy = make_model_info(id="healthy", warmup=True)
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

    async def test_warmup_passes_flagged_voices_of_their_own_model_to_engine_warmup(self):
        """Each warmed engine receives its own warm-up-flagged Voices, and only those."""
        eager = make_model_info(id="eager", warmup=True)
        other = make_model_info(id="other", warmup=True)
        eager_engine = make_engine("eager")
        other_engine = make_engine("other")
        voices = [
            make_voice(voice_id="eager-anna", name="anna", model="eager", warmup=True),
            make_voice(voice_id="eager-not-flagged", name="not_flagged", model="eager"),
            make_voice(voice_id="other-boris", name="boris", model="other", warmup=True),
        ]
        manager, _, _ = make_manager(
            models=[eager, other],
            engines={"eager": eager_engine, "other": other_engine},
            voices=voices,
        )

        await manager.warmup()
        await manager.close()

        assert [voice.id for voice in eager_engine.warmup_voices[0]] == ["eager-anna"]
        assert [voice.id for voice in other_engine.warmup_voices[0]] == ["other-boris"]

    async def test_warmup_slices_voices_to_prompt_cache_capacity(self):
        """No more than `max_voice_prompts` Voices are passed for a model."""
        engine = make_engine()
        voices = [
            make_voice(voice_id=f"eager-voice-{i}", name=f"voice_{i}", model="eager", warmup=True)
            for i in range(3)
        ]
        manager, _, _ = make_manager(
            models=[make_model_info(id="eager", warmup=True)],
            engines={"eager": engine},
            voices=voices,
            max_voice_prompts=2,
        )

        await manager.warmup()
        await manager.close()

        assert [voice.id for voice in engine.warmup_voices[0]] == [
            "eager-voice-0",
            "eager-voice-1",
        ]

    async def test_warmup_slices_voices_per_model_to_prompt_cache_capacity(self):
        """The prompt-cache capacity limits each model's Voices, not all models' pooled."""
        # "second" comes before "first" in the warm-up order, so a pooled slice
        # would hand "second" nothing and starve its engine.
        second = make_model_info(id="second", warmup=True)
        first = make_model_info(id="first", warmup=True)
        second_engine = make_engine("second")
        first_engine = make_engine("first")
        voices = [
            make_voice(voice_id=f"second-voice-{i}", name=f"s_{i}", model="second", warmup=True)
            for i in range(2)
        ] + [
            make_voice(voice_id=f"first-voice-{i}", name=f"f_{i}", model="first", warmup=True)
            for i in range(2)
        ]
        manager, _, _ = make_manager(
            models=[second, first],
            engines={"second": second_engine, "first": first_engine},
            voices=voices,
            max_voice_prompts=1,
        )

        await manager.warmup()
        await manager.close()

        assert [voice.id for voice in second_engine.warmup_voices[0]] == ["second-voice-0"]
        assert [voice.id for voice in first_engine.warmup_voices[0]] == ["first-voice-0"]

    async def test_warmup_sends_no_voices_when_none_are_flagged(self):
        """A warmed engine with no warm-up-flagged Voices gets none."""
        engine = make_engine()
        manager, _, _ = make_manager(
            models=[make_model_info(id=MODEL_ID, warmup=True)],
            engines={MODEL_ID: engine},
            voices=[make_voice_for(MODEL_ID)],
        )

        await manager.warmup()
        await manager.close()

        assert engine.warmup_voices == [[]]

    async def test_warmup_engine_raising_on_voices_is_skipped_and_others_still_load(self):
        """A warmed engine whose Voice Prompt builds fail does not stop the rest."""
        broken = make_model_info(id="broken", warmup=True)
        healthy = make_model_info(id="healthy", warmup=True)
        healthy_engine = make_engine("healthy")
        voices = [
            make_voice(voice_id="broken-anna", name="anna", model="broken", warmup=True),
        ]
        manager, _, _ = make_manager(
            models=[broken, healthy],
            engines={
                "broken": make_engine("broken", warmup_error=RuntimeError("bad voice")),
                "healthy": healthy_engine,
            },
            voices=voices,
        )

        await manager.warmup()
        await manager.close()

        assert healthy_engine.warmup_count == 1

    async def test_warmup_does_nothing_when_models_already_loaded(self):
        """Warmup is a no-op once the manager holds engines."""
        engine = make_engine()
        manager, _, _ = make_manager(
            models=[make_model_info(id=MODEL_ID, warmup=True)], engines={MODEL_ID: engine}
        )

        await manager.warmup()
        await manager.warmup()
        await manager.close()

        assert engine.warmup_count == 1


class TestOnDemandLoading:
    async def test_first_request_loads_engine_and_second_reuses_it(self):
        """A Model Info's engine loads once on first use; later requests reuse it."""
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
        """Asking for a model the storage does not know raises an error naming it."""
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
    async def test_evicted_cached_engine_is_closed_exactly_once(self):
        """Evicting the least-recently-used cached engine closes it once."""
        evicted = make_engine("evicted")
        kept = make_engine("kept")
        manager, _, _ = make_manager(
            models=[make_model_info(id="evicted"), make_model_info(id="kept")],
            engines={"evicted": evicted, "kept": kept},
            cache_capacity=1,
        )

        await synthesize_via(manager, model_id="evicted")
        await synthesize_via(manager, model_id="kept")

        assert await wait_until(lambda: evicted.close_count == 1)
        await manager.close()

        assert evicted.close_count == 1

    async def test_least_recently_used_cached_engine_is_the_one_evicted(self):
        """The recently-used cached engine survives eviction; the idle one is closed."""
        idle = make_engine("idle")
        recent = make_engine("recent")
        newcomer = make_engine("newcomer")
        manager, _, _ = make_manager(
            models=[
                make_model_info(id="idle"),
                make_model_info(id="recent"),
                make_model_info(id="newcomer"),
            ],
            engines={"idle": idle, "recent": recent, "newcomer": newcomer},
            cache_capacity=2,
        )

        await synthesize_via(manager, model_id="idle")
        await synthesize_via(manager, model_id="recent")
        # Touch "idle" so "recent" becomes the least recently used.
        await synthesize_via(manager, model_id="idle")
        await synthesize_via(manager, model_id="newcomer")

        assert await wait_until(lambda: recent.close_count == 1)

        # Before shutdown, only the least recently used cached engine has been torn down.
        assert idle.close_count == 0
        assert recent.close_count == 1

        await manager.close()

        assert idle.close_count == 1

    async def test_cached_engine_in_use_is_closed_only_after_its_request_completes(self):
        """The cached engine held by an in-flight request is deferred, then closed once released."""
        release = asyncio.Event()
        held = make_engine("held", hold=release)
        manager, _, _ = make_manager(
            models=[make_model_info(id="held"), make_model_info(id="other")],
            engines={"held": held},
            cache_capacity=1,
        )

        voice = make_voice_for("held")
        async with await manager.get_context("held") as shared:
            request = asyncio.create_task(
                _drain(shared.synthesize_pcm("hello", voice, TextFormat.TEXT))
            )
            assert await wait_until(lambda: held.active_syntheses == 1, timeout=5.0)

            # Loading a second model evicts "held", but the in-flight request still holds it.
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


class TestQueuedAcquire:
    """A request already queued on the per-Model limit holds the cached engine meanwhile.

    Taking the reference only after the wait would let eviction tear the cached entry
    down underneath a queued waiter, stripping the engine and the very semaphore
    the waiter is blocked on.
    """

    async def test_queued_acquire_defers_eviction_of_the_cached_engine(self):
        """A request waiting for the per-Model limit keeps its cached engine from being closed."""
        release = asyncio.Event()
        held = make_engine("held", hold=release)
        manager, _, _ = make_manager(
            models=[make_model_info(id="held"), make_model_info(id="other")],
            engines={"held": held},
            cache_capacity=1,
            max_concurrent_sentences_per_model=1,
        )
        voice = make_voice_for("held")

        holder = await manager.get_context("held")
        shared = await holder.__aenter__()
        request = asyncio.create_task(
            _drain(shared.synthesize_pcm("hello", voice, TextFormat.TEXT))
        )
        assert await wait_until(lambda: held.active_syntheses == 1, timeout=5.0)

        # A second request queues behind the per-Model limit.
        waiter = asyncio.create_task(synthesize_via(manager, model_id="held"))
        for _ in range(3):
            await asyncio.sleep(0)
        assert not waiter.done(), "the queued request should be waiting on the limit"

        # The holder finishes and releases the limit. The waiter is woken but has not
        # resumed, so it still holds the reference it took before waiting.
        release.set()
        await request
        await holder.__aexit__(None, None, None)

        # Evicting "held" in that window must be deferred, and the cleaner must not
        # strip the engine or the semaphore the waiter is blocked on.
        cached = manager._cache.get("held")
        assert cached is not None
        manager._handle_cache_eviction([("held", cached)])
        await manager._clear_engines(manager._dead_pool.copy())
        manager._dead_pool.clear()

        assert held.close_count == 0, "a queued request must defer eviction"

        await asyncio.wait_for(waiter, timeout=CLEANER_TIMEOUT_SECONDS)
        await manager.close()


class TestCancelledAcquire:
    """A cancelled acquire must leave the cached engine as free as it was before the request.

    The Engine Context takes the cached engine's reference before awaiting the per-Model
    concurrency limit, so a caller cancelled during that wait must give the
    reference back: __aexit__ never runs for a body that was never entered. The
    cached engine then stays free, eviction is not deferred, and the engine is closed on
    schedule.
    """

    async def test_cancelled_acquire_leaves_the_cached_engine_evictable(self):
        """Cancelling a request blocked on the per-Model limit does not pin the cached engine."""
        release = asyncio.Event()
        evictable = make_engine("evictable", hold=release)
        manager, _, _ = make_manager(
            models=[make_model_info(id="evictable"), make_model_info(id="other")],
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

            # A second request for the same model id waits for the concurrency limit.
            # The engine is cached and the limit is taken, so the only await left on
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

        # Loading another model evicts "evictable". A cancelled acquire must not be
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
            models=[make_model_info(id="first"), make_model_info(id="second")],
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
            models=[make_model_info(id="held"), make_model_info(id="other")],
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
