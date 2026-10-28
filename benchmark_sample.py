"""Measure a synthesis request through the whole server stack, in-process.

The server is wired exactly as `src.main` wires it and served on a loopback URI,
then driven with a real Wyoming client. The numbers therefore cover everything a
client waits for: sentence splitting, normalization, engine inference, and the
streaming of Frames.

The vocabulary is the glossary's. A **Sentence** is a segment of the input text
the hub synthesizes separately, a **Chunk** is the audio a TTS Engine produces
for one Sentence, and a **Frame** is the slice of a Chunk that goes to the client.
Reporting all three is the point of this benchmark: they are different counts, and
the gap between them is what tells you where the time went.

    python benchmark_sample.py --voice silero_ru-aidar --repeat 3
"""

import argparse
import asyncio
import resource
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from functools import partial

import torch
from wyoming.audio import AudioChunk, AudioStart
from wyoming.client import AsyncClient
from wyoming.error import Error
from wyoming.server import AsyncServer, AsyncTcpServer
from wyoming.tts import Synthesize, SynthesizeVoice

from src.config import Settings, get_settings
from src.handler import TtsEngineHubEventHandler
from src.main import create_openai_client, setup_backend
from src.tts.data_storage import YamlDataStorage
from src.tts.engine import TtsEngine
from src.tts.engine_factory import TtsEngineFactory
from src.tts.engine_hub import TtsEngineHub
from src.tts.engine_manager import TtsEngineManager
from src.tts.middleware import (
    MiddlewareType,
    NormalizeTextMiddleware,
    ResolveLanguageMiddleware,
    SplitSentencesMiddleware,
    SynthesisContext,
)
from src.tts.models import BackendType, ModelInfo, TextFormat, TtsResult, Voice
from src.tts.preprocessing import TextNormalizerFactory, TextSentencizerFactory

# Long enough to be split into several Sentences: a single Sentence measures one
# inference and says nothing about how the hub pipelines them. One per Language the
# repository ships a Model Info for, because a benchmark that asks a Model Info to speak
# a Language it does not declare measures nothing but the resulting error.
SAMPLE_TEXT: dict[str, str] = {
    "en": (
        "The TTS Engine Hub splits text into Sentences, normalizes each one, and routes it "
        "to the TTS Engine that owns the requested Model Info. Each Sentence comes back as "
        "one or more Chunks, and the Hub streams those to the client as Frames."
    ),
    "ru": (
        "TTS Engine Hub делит текст на предложения, нормализует каждое из них и передаёт их "
        "движку, которому принадлежит запрошенная модель. Каждое предложение возвращается "
        "одним или несколькими фрагментами аудио, и Hub передаёт их клиенту как кадры."
    ),
}


def default_text_for(language: str | None) -> str:
    """Sample text in a Language, falling back to the English one.

    A **Model Info** declares the Languages it can be asked to speak, so the sample has
    to match whichever one the benchmark is about to use.
    """
    return SAMPLE_TEXT.get(language or "", SAMPLE_TEXT["en"])


def audio_duration_seconds(
    audio_bytes: int, *, bytes_per_sample: int, channels: int, sample_rate: int
) -> float:
    """The speech a client received, as seconds of audio."""
    frame_size = bytes_per_sample * channels

    if frame_size <= 0 or sample_rate <= 0:
        return 0.0

    return (audio_bytes // frame_size) / sample_rate


def real_time_factor(elapsed_seconds: float, audio_seconds: float) -> float:
    """Seconds spent synthesizing per second of audio.

    Below 1.0 the server speaks faster than the audio plays.
    """
    if audio_seconds <= 0:
        return 0.0

    return elapsed_seconds / audio_seconds


@dataclass
class SynthesisMeasurement:
    """What one synthesis request cost, counted in the glossary's terms."""

    sentences: int = 0
    chunks: int = 0
    frames: int = 0
    audio_seconds: float = 0.0
    wall_seconds: float = 0.0
    inference_seconds: float = 0.0
    first_audio_seconds: float | None = None
    peak_memory_mb: float | None = None
    peak_memory_source: str = "process peak RSS, lifetime"

    def report(self) -> str:
        """The measurement as a block of aligned lines."""
        rtf = real_time_factor(self.wall_seconds, self.audio_seconds)
        status = "FASTER THAN REAL TIME" if rtf < 1.0 else "SLOWER THAN REAL TIME"
        first_audio = (
            f"{self.first_audio_seconds:.3f} sec" if self.first_audio_seconds is not None else "N/A"
        )
        peak_memory = (
            f"{self.peak_memory_mb:.2f} MB ({self.peak_memory_source})"
            if self.peak_memory_mb is not None
            else "N/A"
        )

        return "\n".join(
            [
                f"Sentences:        {self.sentences}",
                f"Chunks:           {self.chunks}",
                f"Frames:           {self.frames}",
                f"First Frame:      {first_audio}",
                f"Audio duration:   {self.audio_seconds:.2f} sec",
                f"Wall time:        {self.wall_seconds:.3f} sec",
                f"Engine inference: {self.inference_seconds:.3f} sec",
                f"RTF (wall):      {rtf:.3f} ({status})",
                f"Peak memory:      {peak_memory}",
            ]
        )


class SentenceRecorder:
    """A middleware counting the Sentences handed on to synthesis.

    Sits last in the chain, so what it counts is the Sentences after splitting and
    normalization: the units the TTS Engine is actually asked to speak.
    """

    def __init__(self) -> None:
        self.sentences: list[str] = []

    async def __call__(
        self, ctx: SynthesisContext, next_call: Callable[[], Awaitable[None]]
    ) -> None:
        sentences = ctx.sentences

        async def counted() -> AsyncIterator[str]:
            async for sentence in sentences:
                self.sentences.append(sentence)
                yield sentence

        ctx.sentences = counted()
        await next_call()


class CountingTtsEngine(TtsEngine):
    """A TTS Engine counting the Chunks and inference time of the engine it wraps.

    A Chunk here is one piece of the audio the real engine produced for a Sentence,
    before the hub has sliced it into Frames.
    """

    def __init__(self, engine: TtsEngine):
        super().__init__(engine.model_info)
        self._engine = engine
        self.chunks = 0
        self.inference_seconds = 0.0

    @property
    def device(self) -> torch.device | None:
        """The device the wrapped engine synthesized on, when it declares one."""
        return getattr(self._engine, "device", None)

    async def _warmup(self, voices: list[Voice] | None = None) -> bool:
        await self._engine.warmup(voices)

        return True

    async def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        started = time.perf_counter()

        async for chunk in self._engine.synthesize_pcm(text, voice, text_format, language):
            self.chunks += 1
            yield chunk

        self.inference_seconds += time.perf_counter() - started

    async def close(self) -> None:
        await self._engine.close()


class InstrumentedTtsEngineFactory(TtsEngineFactory):
    """A TTS Engine Factory handing back engines that count their own work."""

    def __init__(self, settings: Settings):
        super().__init__(settings=settings)
        self.engines: dict[str, CountingTtsEngine] = {}

    def create(self, model_info: ModelInfo, backendType: BackendType) -> TtsEngine:
        engine = CountingTtsEngine(super().create(model_info, backendType))
        self.engines[model_info.id] = engine

        return engine

    @property
    def chunks(self) -> int:
        """Every Chunk every engine has produced so far."""
        return sum(engine.chunks for engine in self.engines.values())

    @property
    def inference_seconds(self) -> float:
        """Every engine's inference time so far."""
        return sum(engine.inference_seconds for engine in self.engines.values())

    @property
    def device(self) -> torch.device | None:
        """The device of the first engine that declared one."""
        for engine in self.engines.values():
            if engine.device is not None:
                return engine.device

        return None


def device_peak_memory_mb(
    device: torch.device | None, *, reset: bool = False
) -> tuple[float, str] | None:
    """Peak memory on the device, in MB and where it was read.

    `reset` forgets the high-water mark first, so the figure can describe what one run
    cost rather than the whole process. Returns None on cpu, which has no counter
    worth resetting — the caller falls back to the process high-water mark.
    """
    device_type = device.type if device is not None else "cpu"

    if device_type == "cuda" and torch.cuda.is_available():
        if reset:
            torch.cuda.reset_peak_memory_stats(device)

        return torch.cuda.max_memory_allocated(device) / (1024**2), "device peak"
    if device_type == "xpu" and hasattr(torch, "xpu") and torch.xpu.is_available():
        if reset:
            torch.xpu.reset_peak_memory_stats(device)

        return torch.xpu.max_memory_allocated(device) / (1024**2), "device peak"
    if device_type == "mps" and hasattr(torch, "mps"):
        if reset:
            torch.mps.empty_cache()

        return torch.mps.current_allocated_memory() / (1024**2), "device"

    return None


def peak_memory_report(device: torch.device | None, *, reset: bool = False) -> tuple[float, str]:
    """Peak memory for the report: the device's, or the process high-water mark.

    The cpu figure is a lifetime high-water mark and cannot be reset, so it is labelled
    as such rather than passed off as what one request cost.
    """
    measured = device_peak_memory_mb(device, reset=reset)
    if measured is not None:
        return measured

    # ru_maxrss is kibibytes on Linux.
    rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return rss_kib / 1024, "process peak RSS, lifetime"


class BenchmarkStack:
    """The real server wiring, plus the instrumentation this benchmark needs."""

    def __init__(self, settings: Settings):
        setup_backend(settings)

        self.recorder = SentenceRecorder()
        self.engines = InstrumentedTtsEngineFactory(settings=settings)
        self.normalization_client = create_openai_client(settings.normalization.openai)

        self.data_storage = YamlDataStorage(
            config_path_or_model=settings.data_yml_path, active_models=settings.active_models
        )
        self.engine_manager = TtsEngineManager(
            backendType=settings.backend_type,
            cache_half_life_seconds=settings.cache_half_life,
            cache_capacity=settings.max_models,
            inference_timeout=settings.inference_timeout,
            max_concurrent_sentences_per_model=settings.max_concurrent_sentences_per_model,
            engine_factory=self.engines,
            data_storage=self.data_storage,
        )

        middlewares: list[MiddlewareType] = [
            ResolveLanguageMiddleware().invoke,
            SplitSentencesMiddleware(
                max_sentence_chars=settings.max_sentence_chars,
                text_sentencizer_factory=TextSentencizerFactory(),
            ).invoke,
            NormalizeTextMiddleware(
                timeout=settings.normalization.timeout,
                max_concurrent_sentences=settings.normalization.max_concurrent_sentences_per_request,
                text_normalizer_factory=TextNormalizerFactory(
                    openai_client=self.normalization_client,
                    settings=settings.normalization,
                    storage=self.data_storage,
                ),
            ).invoke,
            self.recorder,
        ]

        self.engine_hub = TtsEngineHub(
            frame_duration=settings.frame_duration,
            middlewares=middlewares,
            engine_manager=self.engine_manager,
            data_storage=self.data_storage,
        )

    def handler_factory(self, settings: Settings):
        """Build a handler per connection, as `src.main` does."""
        return partial(
            TtsEngineHubEventHandler,
            self.engine_hub,
            self.data_storage,
            settings.app_name,
            settings.streaming,
            settings.env_type == "development",
        )

    def active_voice(self) -> Voice:
        """The first Voice of an Active Model Info, so the benchmark runs unconfigured."""
        return self.data_storage.get_voices()[0]

    def language_of(self, voice: Voice) -> str | None:
        """The sole Language of the Model Info behind a Voice, when it declares one."""
        model_info = self.data_storage.get_model_info(voice.model_id)

        return model_info.languages[0] if model_info and model_info.languages else None

    async def close(self) -> None:
        await self.engine_manager.close()

        if self.normalization_client is not None:
            await self.normalization_client.close()


async def measure_request(uri: str, voice_id: str, text: str) -> SynthesisMeasurement:
    """Send one synthesis request and measure everything a client waits for."""
    measurement = SynthesisMeasurement()
    announced: AudioStart | None = None
    audio_bytes = 0

    async with AsyncClient.from_uri(uri) as client:
        # Timed from the request, not the connection: connecting is not what a caller waits for.
        started = time.perf_counter()

        # One request, not a stream: no synthesize-start, so no synthesize-stop either.
        await client.write_event(
            Synthesize(text=text, voice=SynthesizeVoice(name=voice_id)).event()
        )

        while True:
            event = await client.read_event()
            if event is None:
                break

            if Error.is_type(event.type):
                raise RuntimeError(Error.from_event(event).text)

            if AudioStart.is_type(event.type):
                announced = AudioStart.from_event(event)
                continue

            # A Frame carries its audio as the event payload; anything else ends the audio.
            if not AudioChunk.is_type(event.type):
                break

            audio_bytes += len(event.payload)
            measurement.frames += 1
            if measurement.first_audio_seconds is None:
                measurement.first_audio_seconds = time.perf_counter() - started

        measurement.wall_seconds = time.perf_counter() - started

    if announced is None:
        raise RuntimeError("The server announced no audio format, so it synthesized nothing")

    measurement.audio_seconds = audio_duration_seconds(
        audio_bytes,
        bytes_per_sample=announced.width,
        channels=announced.channels,
        sample_rate=announced.rate,
    )

    return measurement


async def serve_on(uri: str, handler_factory) -> tuple[str, AsyncServer]:
    """Serve the stack on `uri`, returning the URI actually bound.

    Port 0 asks the OS for a free port, so a benchmark never collides with a running
    server on the configured one.
    """
    server = AsyncServer.from_uri(uri)
    await server.start(handler_factory)

    bound = uri
    if isinstance(server, AsyncTcpServer) and server.port == 0:
        sockets = getattr(server._server, "sockets", None) or []
        if sockets:
            host, port = sockets[0].getsockname()[:2]
            bound = f"tcp://{host}:{port}"

    return bound, server


async def run_benchmark(
    *, uri: str, voice_id: str | None, text: str | None, repeat: int
) -> SynthesisMeasurement:
    """Serve the stack, send `repeat` requests, and report the last one.

    Every Model Info asking to be warmed up is warmed before measuring, as the server
    warms them at startup, so no request here pays for loading a model. `repeat` is
    for taking a second look at a request that is already warm.
    """
    settings = get_settings()
    stack = BenchmarkStack(settings)
    voice = (
        next(
            (v for v in stack.data_storage.get_voices() if v.id == voice_id),
            None,
        )
        or stack.active_voice()
    )
    requested_text = text or default_text_for(stack.language_of(voice))

    await stack.engine_manager.warmup()
    bound_uri, server = await serve_on(uri, stack.handler_factory(settings))

    measurement = SynthesisMeasurement()
    seen_sentences = 0
    seen_chunks = 0
    seen_inference_seconds = 0.0

    try:
        for _ in range(repeat):
            # Only now does a device exist, so this is the first point a device peak
            # can be measured from rather than inherited from warmup.
            peak_memory_mb, peak_memory_source = peak_memory_report(
                stack.engines.device, reset=True
            )
            measurement = await measure_request(bound_uri, voice.id, requested_text)
            measurement.peak_memory_mb = peak_memory_mb
            measurement.peak_memory_source = peak_memory_source

            sentences = len(stack.recorder.sentences)
            chunks = stack.engines.chunks
            inference_seconds = stack.engines.inference_seconds

            measurement.sentences = sentences - seen_sentences
            measurement.chunks = chunks - seen_chunks
            measurement.inference_seconds = inference_seconds - seen_inference_seconds

            seen_sentences = sentences
            seen_chunks = chunks
            seen_inference_seconds = inference_seconds
    finally:
        await server.stop()
        await stack.close()

    return measurement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark a synthesis request end to end.")
    parser.add_argument(
        "--uri",
        default="tcp://127.0.0.1:0",
        help="URI to serve the benchmark on; port 0 takes a free port",
    )
    parser.add_argument("--voice", default=None, help="Voice to synthesize")
    parser.add_argument(
        "--text",
        default=None,
        help="Text to synthesize; defaults to a sample in the Voice's Language",
    )
    parser.add_argument(
        "--repeat", type=int, default=1, help="Requests to send; only the last is reported"
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    measurement = asyncio.run(
        run_benchmark(uri=args.uri, voice_id=args.voice, text=args.text, repeat=args.repeat)
    )

    print(measurement.report())


if __name__ == "__main__":
    main()
