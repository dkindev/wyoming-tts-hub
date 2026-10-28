import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from loguru import logger

from src.tts.data_storage import DataStorage
from src.tts.engine import TorchTtsEngine, TtsEngine
from src.tts.engine_cache import ExponentialDecayCache
from src.tts.engine_factory import TtsEngineFactory
from src.tts.models import BackendType, ModelInfo, TextFormat, TtsResult, Voice

# Torch device namespaces whose accelerator cache is released after teardown.
CACHE_CLEARABLE_DEVICES = frozenset({"cuda", "mps", "xpu"})

# How often the background worker drains engines that are no longer in use.
CLEANER_INTERVAL_SECONDS = 3.0


def _take_engine(cached: "CachedTtsEngine | None") -> TtsEngine | None:
    """Detach and return a cached engine, or None when it has already been freed.

    Teardown can run twice over the same batch — a background cleaner mid-pass while
    shutdown drains the same engines — so releasing an engine must be idempotent.
    """
    if cached is None:
        return None

    engine = getattr(cached, "engine", None)
    if engine is None:
        return None

    del cached.engine
    return engine


@dataclass
class CachedTtsEngine:
    """Bundles a loaded engine with its concurrency control."""

    engine: TtsEngine
    semaphore: asyncio.Semaphore


class TtsEngineContext:
    def __init__(
        self,
        model_id: str,
        cached_engine: CachedTtsEngine,
        inference_timeout: float,
        acquire_engine_ref: Callable[[str], None],
        release_engine_ref: Callable[[str, CachedTtsEngine], None],
    ):
        self._model_id = model_id
        self._cached_engine = cached_engine
        self._inference_timeout = inference_timeout
        self._acquire_engine_ref = acquire_engine_ref
        self._release_engine_ref = release_engine_ref

    async def __aenter__(self):
        # The reference is taken before the wait so that eviction is deferred for a
        # request already queued on the limit: tearing the cached engine down under a
        # queued waiter would strip the engine and the semaphore it is blocked on.
        # A cancelled wait therefore has to give the reference back, since __aexit__
        # never runs for a body that was never entered.
        self._acquire_engine_ref(self._model_id)

        try:
            await self._cached_engine.semaphore.acquire()
        except asyncio.CancelledError:
            self._release_engine_ref(self._model_id, self._cached_engine)
            raise

        self._acquired = True
        return ImmutableSharedTtsEngine(
            inference_timeout=self._inference_timeout, engine=self._cached_engine.engine
        )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._acquired:
                self._cached_engine.semaphore.release()
        finally:
            self._acquired = False
            self._release_engine_ref(self._model_id, self._cached_engine)


class ImmutableSharedTtsEngine(TtsEngine):
    def __init__(
        self,
        inference_timeout: float,
        engine: TtsEngine,
    ):
        super().__init__(engine.model_info)

        self._inference_timeout = inference_timeout
        self._engine = engine

    async def warmup(self, voices: list[Voice] | None = None) -> None:
        raise RuntimeError("Manual warmup is forbidden.")

    async def close(self) -> None:
        raise RuntimeError("Manual close is forbidden.")

    async def synthesize_pcm(
        self, text: str, voice: Voice, text_format: TextFormat, language: str | None = None
    ) -> AsyncIterator[TtsResult]:
        engine_generator = self._engine.synthesize_pcm(
            text=text, voice=voice, text_format=text_format, language=language
        ).__aiter__()

        async with contextlib.aclosing(engine_generator) as iterator:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        iterator.__anext__(), timeout=self._inference_timeout
                    )
                    yield chunk
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    logger.error(
                        f"[Timeout] Chunk timeout exceeded ({self._inference_timeout}с) "
                        f"for model '{voice.model_id}'"
                    )
                    raise

    async def _warmup(self, voices: list[Voice] | None = None) -> bool:
        raise NotImplementedError()

    def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        raise NotImplementedError()


class TtsEngineManager:
    def __init__(
        self,
        backendType: BackendType,
        cache_half_life_seconds: float,
        cache_capacity: int,
        inference_timeout: float,
        max_concurrent_sentences_per_model: int,
        engine_factory: TtsEngineFactory,
        data_storage: DataStorage,
        max_voice_prompts: int = 8,
    ):
        self._closed = False
        self._backendType = backendType
        self._cache_capacity = cache_capacity
        self._inference_timeout = inference_timeout
        self._max_concurrent_sentences_per_model = max_concurrent_sentences_per_model
        self._max_voice_prompts = max_voice_prompts
        self._engine_factory = engine_factory
        self._data_storage = data_storage
        self._global_lock = asyncio.Lock()
        self._model_locks: dict[str, asyncio.Lock] = {}
        self._cache = ExponentialDecayCache(
            capacity=cache_capacity,
            half_life_seconds=cache_half_life_seconds,
            on_evict=self._handle_cache_eviction,
        )
        self._ref_counts: dict[str, int] = {}
        self._pending_eviction: dict[str, CachedTtsEngine] = {}
        self._dead_pool: list[tuple[str, CachedTtsEngine]] = []
        self._cleaner_task = asyncio.create_task(self._cleaner_worker())
        self._current_destroying_batch = []

    async def warmup(self):
        if self._closed:
            raise RuntimeError("Engine manager is closed")

        async with self._global_lock:
            if len(self._cache) > 0:
                logger.debug("Warmup skipped: models are already in the cache.")
                return

            logger.info("Warming up...")

            models = self._data_storage.get_model_infos()
            to_warm = [model_info for model_info in models if model_info.warmup][
                : self._cache_capacity
            ]

            logger.debug("Models to warm up: {count}", count=len(to_warm))

            warmup_voices = [voice for voice in self._data_storage.get_voices() if voice.warmup]

            for model_info in to_warm:
                try:
                    cached_engine = await self._warmup_engine(model_info, warmup_voices)
                except Exception:
                    logger.exception(
                        "Failed to warm up model '{model_id}'. Skipping.", model_id=model_info.id
                    )
                    continue

                self._cache.put(model_info.id, cached_engine)

            logger.info(f"Warmup completed. Loaded {len(self._cache)} models.")

    async def get_context(self, model_id: str) -> TtsEngineContext:
        if self._closed:
            raise RuntimeError("Engine manager is closed")

        model_lock: asyncio.Lock | None = None

        def create_context(cached_engine: CachedTtsEngine):
            return TtsEngineContext(
                model_id=model_id,
                cached_engine=cached_engine,
                inference_timeout=self._inference_timeout,
                acquire_engine_ref=self._acquire_engine_ref,
                release_engine_ref=self._release_engine_ref,
            )

        async with self._global_lock:
            cached = self._cache.get(model_id)
            if cached is not None:
                return create_context(cached)

            if model_id not in self._model_locks:
                self._model_locks[model_id] = asyncio.Lock()
            model_lock = self._model_locks[model_id]

        try:
            async with model_lock:
                if self._closed:
                    raise RuntimeError("Engine manager is closed")

                cached = self._cache.get(model_id)
                if cached is not None:
                    return create_context(cached)

                logger.debug("Model '{name}' not found in cache. Warming up...", name=model_id)

                model_info = self._data_storage.get_model_info(model_id)
                if not model_info:
                    raise RuntimeError(f"Model '{model_id}' not found")

                cached = await self._warmup_engine(model_info)

                async with self._global_lock:
                    if self._closed:
                        self._dead_pool.append((model_id, cached))
                        raise RuntimeError("ModelManager was closed during model warmup")

                    self._cache.put(model_info.id, cached)

                return create_context(cached)

        finally:
            async with self._global_lock:
                if model_id in self._model_locks and not model_lock.locked():
                    del self._model_locks[model_id]

    async def _warmup_engine(
        self, model_info: ModelInfo, warmup_voices: list[Voice] | None = None
    ) -> CachedTtsEngine:
        engine = self._engine_factory.create(model_info, self._backendType)
        # Prompt-cache capacity caps each model's Voices: a model's own flagged voices
        # must not be displaced by another model's filling the slice.
        model_voices = [voice for voice in warmup_voices or [] if voice.model_id == model_info.id][
            : self._max_voice_prompts
        ]
        await engine.warmup(voices=model_voices)

        return CachedTtsEngine(
            engine=engine,
            semaphore=asyncio.Semaphore(value=self._max_concurrent_sentences_per_model),
        )

    def _handle_cache_eviction(self, batch: list[tuple[str, CachedTtsEngine]]):
        for model_id, engine in batch:
            task_count = self._ref_counts.get(model_id, 0)
            if task_count > 0:
                self._pending_eviction[model_id] = engine
                logger.warning(
                    "Deletion of model '{model}' postponed: it is being used by {task_count} tasks.",
                    model=model_id,
                    task_count=task_count,
                )
            else:
                self._dead_pool.append((model_id, engine))

    def _acquire_engine_ref(self, model_id: str):
        self._ref_counts[model_id] = self._ref_counts.get(model_id, 0) + 1

    def _release_engine_ref(self, model_id: str, cached_engine: CachedTtsEngine):
        if model_id not in self._ref_counts:
            return

        self._ref_counts[model_id] -= 1

        if self._ref_counts[model_id] <= 0:
            del self._ref_counts[model_id]

            if model_id in self._pending_eviction:
                del self._pending_eviction[model_id]
                self._dead_pool.append((model_id, cached_engine))

    async def _cleaner_worker(self):
        interval = CLEANER_INTERVAL_SECONDS
        while True:
            try:
                await asyncio.sleep(interval)

                if self._dead_pool:
                    self._current_destroying_batch = self._dead_pool.copy()
                    self._dead_pool.clear()

                if self._current_destroying_batch:
                    await self._clear_engines(self._current_destroying_batch)
                    self._current_destroying_batch = []
            except asyncio.CancelledError:
                logger.debug("Cleanup background worker has been stopped")
                raise
            except Exception:
                logger.exception("Error was occured when clearing the models resources")

    async def _clear_engines(self, engines_to_destroy: list[tuple[str, CachedTtsEngine]]):  # noqa: C901
        batch_count = len(engines_to_destroy)
        logger.debug("Freeing up models resources. Models count: {count}", count=batch_count)

        for model_id, cached in engines_to_destroy:
            engine = _take_engine(cached)
            if engine is None:
                continue
            try:
                await engine.close()
            except Exception:
                logger.exception(
                    "Error was occured when calling close() for engine with model '{model}'",
                    model=model_id,
                )

        def _force_garbage_collect():
            import gc

            devices_needing_cache_clear = set()

            for _, cached in engines_to_destroy:
                engine = _take_engine(cached)
                if engine is None:
                    continue

                if isinstance(engine, TorchTtsEngine):
                    devices_needing_cache_clear.add(engine.device.type)

                del cached.semaphore

            gc.collect()

            if self._backendType is BackendType.TORCH:
                import torch

                for device_type in devices_needing_cache_clear & CACHE_CLEARABLE_DEVICES:
                    getattr(torch, device_type).empty_cache()

        await asyncio.to_thread(_force_garbage_collect)

        for i in range(len(engines_to_destroy)):
            engines_to_destroy[i] = None

        logger.info("{count} model(s) has been successfully deleted", count=batch_count)

    async def close(self):  # noqa: C901
        if self._closed:
            return

        async with self._global_lock:
            if self._closed:
                return

            self._closed = True

            external_cancelled = False

            try:
                if self._cleaner_task and not self._cleaner_task.done():
                    self._cleaner_task.cancel()
                    try:
                        await self._cleaner_task
                    except asyncio.CancelledError:
                        current_task = asyncio.current_task()
                        if current_task and current_task.cancelling() > 0:
                            external_cancelled = True
                        pass

                try:
                    await self._cache.close()
                except asyncio.CancelledError:
                    external_cancelled = True
                except Exception:
                    logger.exception("Error closing the internal cache")

                if external_cancelled:
                    raise asyncio.CancelledError()

            except asyncio.CancelledError:
                logger.warning(
                    "Manager's graceful shutdown process was interrupted by an external cancellation"
                )
                raise

            finally:
                final_batch = []

                if self._current_destroying_batch:
                    final_batch.extend(self._current_destroying_batch)
                    self._current_destroying_batch = []

                if self._dead_pool:
                    final_batch.extend(self._dead_pool)
                    self._dead_pool.clear()

                if self._pending_eviction:
                    final_batch.extend(
                        ((model_id, engine) for model_id, engine in self._pending_eviction.items())
                    )
                    self._pending_eviction.clear()

                self._model_locks.clear()

                if final_batch:
                    try:
                        await asyncio.shield(self._clear_engines(final_batch))
                    except asyncio.CancelledError:
                        logger.warning(
                            "The close() method was interrupted by an external timeout. Memory disposal has been moved to the background"
                        )
                        raise

        logger.info("Engine manager successfully closed, all resources cleared")
