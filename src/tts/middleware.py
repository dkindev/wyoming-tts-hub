import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from loguru import logger

from src.tts.models import Model, TextFormat, Voice
from src.tts.preprocessing import TextNormalizer, TextNormalizerFactory, TextSentenizerFactory


class SynthesisContext:
    def __init__(
        self,
        text: str,
        model: Model,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ):
        self.raw_text = text
        self.model = model
        self.voice = voice
        self.text_format = text_format
        self.language = language
        self.sentences: AsyncIterator[str] = self._init_source()

    async def _init_source(self) -> AsyncIterator[str]:
        yield self.raw_text


MiddlewareType = Callable[[SynthesisContext, Callable[[], Awaitable[None]]], Awaitable[None]]


class DetectLanguageMiddleware:
    def __init__(self):
        pass

    async def invoke(self, ctx: SynthesisContext, next_call: Callable[[], Awaitable[None]]):
        ctx.language = "ru"
        await next_call()


class SplitSentencesMiddleware:
    def __init__(self, max_sentence_chars: int, text_sentenizer_factory: TextSentenizerFactory):
        self._max_sentence_chars = max_sentence_chars
        self._text_sentenizer_factory = text_sentenizer_factory

    async def invoke(self, ctx: SynthesisContext, next_call: Callable[[], Awaitable[None]]):
        text_sentenizer = self._text_sentenizer_factory.create(ctx.text_format, ctx.language)
        if text_sentenizer is None:
            raise RuntimeError(
                f"Text sentenizer not found for voice '{ctx.voice.id}' and '{ctx.language if ctx.language else 'None'}' language"
            )

        logger.debug(
            "Convert text into sentences using '{text_sentenizer}'",
            text_sentenizer=text_sentenizer.__class__.__name__,
        )

        sentences = ctx.sentences

        async def make_aiter() -> AsyncIterator[str]:
            async for sentence in sentences:
                for splitted_sentence in text_sentenizer.text_to_sentences(
                    sentence, self._max_sentence_chars
                ):
                    yield splitted_sentence

        ctx.sentences = make_aiter()
        await next_call()


class NormalizeTextMiddleware:
    def __init__(
        self,
        timeout: float,
        max_concurrent_sentences: int,
        text_normalizer_factory: TextNormalizerFactory,
    ):
        self._timeout = timeout
        self._max_concurrent_sentences = max_concurrent_sentences
        self._text_normalizer_factory = text_normalizer_factory

    async def invoke(self, ctx: SynthesisContext, next_call: Callable[[], Awaitable[None]]):
        if not ctx.language:
            await next_call()
            return

        text_normalizer = self._text_normalizer_factory.create(
            ctx.voice, ctx.text_format, ctx.language
        )
        if text_normalizer is None:
            await next_call()
            return

        logger.debug(
            "Normalize text using '{text_normalizer}'",
            text_normalizer=text_normalizer.__class__.__name__,
        )

        ctx.sentences = self._normalize_text(text_normalizer, ctx.sentences)
        await next_call()

    async def _normalize_text(self, normalizer: TextNormalizer, sentences: AsyncIterator[str]):
        queue = asyncio.Queue(maxsize=3)
        active_tasks = set()

        producer_task = asyncio.create_task(
            self._queue_sentences(
                sentences,
                normalizer,
                queue,
                active_tasks,
            )
        )

        active_tasks.add(producer_task)
        producer_task.add_done_callback(active_tasks.discard)

        try:
            while True:
                if queue.empty() and producer_task.done():
                    producer_task.result()
                    break

                future = await queue.get()
                if future is None:
                    queue.task_done()
                    break

                try:
                    yield await future
                finally:
                    queue.task_done()
        finally:
            for task in list(active_tasks):
                if not task.done():
                    task.cancel()

            if active_tasks:
                await asyncio.gather(*active_tasks, return_exceptions=True)

    async def _queue_sentences(
        self,
        sentences: AsyncIterator[str],
        normalizer: TextNormalizer,
        queue: asyncio.Queue,
        active_tasks: set,
    ):
        semaphore = asyncio.Semaphore(self._max_concurrent_sentences)
        loop = asyncio.get_running_loop()

        try:
            async for sentence in sentences:
                future = loop.create_future()

                await queue.put(future)

                logger.debug("Sentence queued for normalizing. Text: {sentence}", sentence=sentence)

                task = asyncio.create_task(
                    self._process_sentence(sentence, normalizer, semaphore, future)
                )

                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)
        finally:
            if not asyncio.current_task().cancelled():
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

    async def _process_sentence(
        self,
        sentence: str,
        normalizer: TextNormalizer,
        semaphore: asyncio.Semaphore,
        future: asyncio.Future,
    ) -> str:
        if future.done():
            return

        try:
            async with semaphore:
                if future.done():
                    return

                normalized_sentence = await asyncio.wait_for(
                    normalizer.normalize_text(sentence),
                    timeout=self._timeout,
                )

                if not future.done():
                    future.set_result(normalized_sentence)
        except (TimeoutError, asyncio.CancelledError):
            if not future.done():
                future.cancel()
        except Exception as e:
            if not future.done():
                future.set_exception(e)
