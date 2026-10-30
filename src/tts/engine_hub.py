import asyncio
import contextlib
from collections.abc import AsyncIterator, Iterator

from loguru import logger

from src.tts.data_storage import DataStorage
from src.tts.engine_manager import TtsEngineContext, TtsEngineManager
from src.tts.middleware import MiddlewareType, SynthesisContext
from src.tts.models import (
    ModelInfo,
    TextFormat,
    TtsResult,
)


class TtsEngineHub:
    def __init__(
        self,
        frame_duration: float,
        middlewares: list[MiddlewareType],
        engine_manager: TtsEngineManager,
        data_storage: DataStorage,
    ):
        self._frame_duration = frame_duration
        self._middlewares = middlewares
        self._engine_manager = engine_manager
        self._data_storage = data_storage

    async def synthesize_pcm_chunks(
        self,
        text: str,
        voice_id: str,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        text = text.strip()
        if not text:
            raise ValueError("Text is empty or whitespace")

        voice = self._data_storage.get_voice(voice_id)
        if voice is None:
            raise ValueError(f"Unsupported voice: {voice_id}")

        model_info = self._data_storage.get_model_info(voice.model_id)
        if model_info is None:
            raise ValueError(f"Unsupported model: {voice.model_id}")

        ctx = SynthesisContext(text, model_info, voice, text_format, language)

        async with contextlib.aclosing(self._chain(0, ctx)) as audio:
            async for chunk in audio:
                yield chunk

    def _chain(self, index: int, context: SynthesisContext) -> AsyncIterator[TtsResult]:
        """Wrap the terminal synthesis in the middleware from `index` outwards."""
        if index == len(self._middlewares):
            return self._terminal(context)

        next_audio = self._chain(index + 1, context)
        middleware_audio = self._middlewares[index](context, lambda: next_audio)

        return self._forward_and_close(middleware_audio, next_audio)

    async def _forward_and_close(
        self,
        middleware_audio: AsyncIterator[TtsResult],
        next_audio: AsyncIterator[TtsResult],
    ) -> AsyncIterator[TtsResult]:
        """Pass a middleware's audio through, closing both streams when the client stops."""
        try:
            async with contextlib.aclosing(middleware_audio) as audio:
                async for result in audio:
                    yield result
        finally:
            await next_audio.aclose()

    async def _terminal(self, context: SynthesisContext) -> AsyncIterator[TtsResult]:
        """Validate the request and synthesize, after every middleware's pre-processing."""
        self._validate_language(context)
        self._validate_text_format(context)

        model_info = context.model_info
        engine_context = await self._engine_manager.get_context(model_info.id)
        if engine_context is None:
            raise ValueError(f"No engine found for synthesis with model '{model_info.id}'")

        logger.info(
            "Synthesizing TTS. Text length: {text_length}. Voice: {voice_id}. Text format: {text_format}. Model: {model_id}",
            text_length=len(context.raw_text),
            voice_id=context.voice.id,
            text_format=context.text_format.value,
            model_id=model_info.id,
        )

        async for chunk in self._synthesize_pcm_chunks(context, engine_context):
            yield chunk

    @staticmethod
    def _validate_language(context: SynthesisContext) -> None:
        """Reject a request whose Language the Model Info cannot be asked to speak.

        Runs on the Language as it stands after the middleware chain, so a
        middleware is trusted to have resolved it.
        """
        model_info = context.model_info

        def _declared(info: ModelInfo) -> str:
            """The Languages a Model Info declares, phrased for an error message."""
            return ", ".join(info.languages)

        if context.language is None:
            if model_info.language_auto_detected:
                return

            raise ValueError(
                f"No Language given for model '{model_info.id}', which declares: "
                f"{_declared(model_info)} and does not auto-detect its Language"
            )

        if not model_info.languages:
            # Nothing to validate against, so the Language can only be honoured on
            # the Model Info's own say-so.
            if model_info.language_auto_detected:
                return

            raise ValueError(
                f"Language '{context.language}' cannot be checked: model '{model_info.id}' "
                f"declares no Languages and does not auto-detect its Language"
            )

        if context.language not in model_info.languages:
            raise ValueError(
                f"Language '{context.language}' is not declared by model '{model_info.id}', "
                f"which declares: {_declared(model_info)}"
            )

    @staticmethod
    def _validate_text_format(context: SynthesisContext) -> None:
        """Reject a Text Format the Model Info has not declared support for.

        Runs alongside the Language check, on the Text Format as it stands after the
        middleware chain, so a middleware is trusted to have resolved it. Only SSML is
        gated: a Model Info declares whether it accepts SSML, and plain text needs no
        declaration.
        """
        model_info = context.model_info

        if context.text_format != TextFormat.SSML or model_info.ssml_supported:
            return

        raise ValueError(
            f"Text Format '{context.text_format.value}' is not declared by model "
            f"'{model_info.id}', which does not accept SSML"
        )

    async def _synthesize_pcm_chunks(  # noqa: C901
        self,
        context: SynthesisContext,
        engine_context: TtsEngineContext,
    ) -> AsyncIterator[TtsResult]:
        sentence_queue = asyncio.Queue(maxsize=3)
        active_tasks = set()

        producer_task = asyncio.create_task(
            self._queue_sentences(
                context,
                engine_context,
                sentence_queue,
                active_tasks,
            )
        )

        active_tasks.add(producer_task)
        producer_task.add_done_callback(active_tasks.discard)

        try:
            while True:
                if sentence_queue.empty() and producer_task.done():
                    exc = producer_task.exception()
                    if exc:
                        raise exc
                    break

                chunks_queue = await sentence_queue.get()

                try:
                    while True:
                        chunk = await chunks_queue.get()

                        try:
                            if chunk is None:
                                break

                            if isinstance(chunk, Exception):
                                raise chunk

                            for frame in self._generate_frames(chunk):
                                yield frame

                        finally:
                            chunks_queue.task_done()

                    logger.debug("Audio frames for sentence have been sent.")
                except Exception as e:
                    raise RuntimeError("Sentence inference error") from e
                finally:
                    sentence_queue.task_done()
        finally:
            for task in list(active_tasks):
                if not task.done():
                    task.cancel()

            while not sentence_queue.empty():
                try:
                    sentence_queue.get_nowait()
                    sentence_queue.task_done()
                except asyncio.QueueEmpty:
                    break

            if active_tasks:
                await asyncio.gather(*active_tasks, return_exceptions=True)

    async def _queue_sentences(
        self,
        context: SynthesisContext,
        engine_context: TtsEngineContext,
        sentence_queue: asyncio.Queue,
        active_tasks: set,
    ):
        async with contextlib.aclosing(context.sentences) as sentences_stream:
            async for sentence in sentences_stream:
                chunks_queue = asyncio.Queue(maxsize=10)

                task = asyncio.create_task(
                    self._process_sentence(engine_context, sentence, context, chunks_queue)
                )
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

                await sentence_queue.put(chunks_queue)
                logger.debug("Sentence queued for inferencing. Text: {sentence}", sentence=sentence)

    async def _process_sentence(
        self,
        engine_context: TtsEngineContext,
        sentence: str,
        context: SynthesisContext,
        chunks_queue: asyncio.Queue,
    ):
        try:
            async with engine_context as engine:
                async for chunk in engine.synthesize_pcm(
                    sentence, context.voice, context.text_format, context.language
                ):
                    await chunks_queue.put(chunk)
                    logger.debug("Chunk inferenced. Text: {chunk_text}", chunk_text=sentence)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await chunks_queue.put(e)
        finally:
            try:
                chunks_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    def _generate_frames(self, chunk: TtsResult) -> Iterator[TtsResult]:
        """Split one engine chunk into frames of `frame_duration` milliseconds each.

        Each frame is a view over the chunk's audio rather than a copy of it, so a
        Sentence costs one buffer of audio however many frames it is streamed in.
        """
        duration_sec = self._frame_duration / 1000.0
        samples_per_frame = max(int(chunk.sample_rate * duration_sec), 1)
        total_samples = chunk.audio.shape[0]

        for i in range(0, total_samples, samples_per_frame):
            yield TtsResult(
                audio=chunk.audio[i : i + samples_per_frame],
                sample_rate=chunk.sample_rate,
                bytes_per_sample=chunk.bytes_per_sample,
                channels=chunk.channels,
            )
