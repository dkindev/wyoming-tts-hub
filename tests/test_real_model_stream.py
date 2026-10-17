"""Prove a real Model still streams the audio it synthesized, with no network.

Every other test substitutes the Silero package importer, so the suite cannot catch a
break between a real Model's tensor and the bytes a client receives: it can only show
that fakes survive the trip. This module loads a Model already cached under `models/`
and runs it through the real wiring — storage, engine factory, Engine Manager, TTS Engine
Hub and Wyoming handler — then decodes the stream back the way a client would.

Unlike the rest of the suite this reads files from the checkout, which is the point: it
reads none of them unless a Model is cached, and skips instead when none is. Run it with:

    pytest tests/test_real_model_stream.py -v

It needs `models/silero/models.yml` and `models/silero/ru/v5_5_ru.pt` to exist, and it
touches no network: every download is blocked for the duration of the synthesis.
"""

import asyncio
import contextlib
import unittest.mock
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml
from wyoming.tts import (
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeVoice,
)

from src.config import Settings, SileroSettings
from src.handler import TtsEngineHubEventHandler
from src.tts.data_storage import YamlDataStorage
from src.tts.engine import TtsEngine
from src.tts.engine_factory import TtsEngineFactory
from src.tts.engine_hub import TtsEngineHub
from src.tts.engine_manager import TtsEngineManager
from src.tts.middleware import (
    NormalizeTextMiddleware,
    ResolveLanguageMiddleware,
    SplitSentencesMiddleware,
)
from src.tts.models import BackendType, ModelInfo, TextFormat, TtsResult, Voice
from src.tts.preprocessing import TextNormalizerFactory, TextSentencizerFactory
from tests.helpers import (
    AudioFormat,
    WyomingClient,
    announced_audio_format,
    audio_formats,
    streamed_audio_bytes,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_YML_PATH = REPO_ROOT / "data" / "data.yml"
MODELS_DIR = REPO_ROOT / "models"
REGISTRY_PATH = MODELS_DIR / "silero" / "models.yml"

MODEL_ID = "v5_5_ru"
LANGUAGE = "ru"
VOICE_ID = f"{MODEL_ID}-aidar"
TEXT = "Это проверка потоковой передачи аудио."

PCM_DTYPE = np.int16

# The rate the check asks the Model for. The Model publishes several rates, so this
# is the only one of them a client should be told about: the one it synthesized at.
CONFIGURED_SAMPLE_RATE = 48000

# The format the Silero engine hands over: 16-bit samples, one channel.
EXPECTED_WIDTH = 2
EXPECTED_CHANNELS = 1

# Speech the Model produced has to be at least this loud, out of full scale, for the
# check to mean anything: silence passes every byte comparison there is.
MIN_PEAK_AMPLITUDE = 1000


class AudioRecordingTtsEngine(TtsEngine):
    """A real TTS Engine that keeps every Chunk it synthesized.

    The audio a Model produces is the only account of what a client *should* receive,
    so it is kept here rather than inferred from the stream being checked.
    """

    def __init__(self, engine: TtsEngine):
        super().__init__(engine.model_info)
        self._engine = engine
        self.synthesized: list[TtsResult] = []

    async def _warmup(self) -> bool:
        await self._engine.warmup()
        return True

    async def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ):
        async for chunk in self._engine.synthesize_pcm(text, voice, text_format, language):
            self.synthesized.append(chunk)
            yield chunk


class RecordingTtsEngineFactory(TtsEngineFactory):
    """A TTS Engine Factory whose engines record the audio they synthesized."""

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.recordings: list[AudioRecordingTtsEngine] = []

    def create(self, model_info: ModelInfo, backendType: BackendType) -> TtsEngine:
        engine = AudioRecordingTtsEngine(super().create(model_info, backendType))
        self.recordings.append(engine)
        return engine


@dataclass(frozen=True)
class StreamedRequest:
    """One real synthesis: the Chunks a Model produced and the events a client read."""

    synthesized: list[TtsResult]
    events: list

    @property
    def synthesized_samples(self) -> int:
        """Total samples the Model synthesized, which is what a client should have heard."""
        return sum(chunk.audio.shape[0] for chunk in self.synthesized)

    @property
    def synthesized_seconds(self) -> float:
        """How many seconds of audio the Model produced, at the rate it produced it."""
        return self.synthesized_samples / self.format.rate

    @property
    def format(self) -> AudioFormat:
        """The format the handler announced to the client."""
        return announced_audio_format(self.events)

    @property
    def received(self) -> np.ndarray:
        """The audio a client decoded off the wire."""
        return np.frombuffer(streamed_audio_bytes(self.events), dtype=PCM_DTYPE)


def published_sample_rates() -> list[int]:
    """The sample rates the cached registry says the Model speaks, or [] if uncached."""
    if not REGISTRY_PATH.is_file():
        return []

    registry = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    model = registry.get("tts_models", {}).get(LANGUAGE, {}).get(MODEL_ID, {})
    return model.get("latest", {}).get("sample_rate", [])


def cached_model_path() -> Path | None:
    """The cached Silero package for the Model this check synthesizes with, if there is one."""
    path = MODELS_DIR / "silero" / LANGUAGE / f"{MODEL_ID}.pt"
    return path if path.is_file() else None


def synthesized_bytes(chunks: list[TtsResult]) -> bytes:
    """The audio a Model produced, as the bytes a client should have received."""
    return b"".join(chunk.audio.tobytes() for chunk in chunks)


@contextlib.contextmanager
def blocking_downloads():
    """Patch every download so that reaching for the network is an error, and record it.

    The check is meant to prove the Model is served from disk, so a run that reaches
    for the network fails instead of quietly succeeding on a connected machine. The
    patches are yielded by name, so a caller can assert none of them fired.
    """

    def refuse(*args, **kwargs):
        raise AssertionError("the check must not touch the network")

    with (
        unittest.mock.patch.object(
            urllib.request, "urlretrieve", side_effect=refuse
        ) as urlretrieve,
        unittest.mock.patch.object(
            torch.hub, "download_url_to_file", side_effect=refuse
        ) as download_url_to_file,
    ):
        yield {"urlretrieve": urlretrieve, "download_url_to_file": download_url_to_file}


def make_settings() -> Settings:
    """Settings for the check, pointing at the repository's cached Models."""
    return Settings(
        active_models=[MODEL_ID],
        data_yml_path=str(DATA_YML_PATH),
        models_dir=str(MODELS_DIR),
        frame_duration=50,
        inference_timeout=60,
        silero=SileroSettings(sample_rate=CONFIGURED_SAMPLE_RATE),
    )


async def synthesize_and_read(settings: Settings) -> StreamedRequest:
    """Synthesize `TEXT` through the real wiring and read back what a client would."""
    storage = YamlDataStorage(
        config_path_or_model=settings.data_yml_path, active_models=settings.active_models
    )
    factory = RecordingTtsEngineFactory(settings=settings)
    engine_manager = TtsEngineManager(
        backendType=settings.backend_type,
        cache_half_life_seconds=settings.cache_half_life,
        cache_capacity=settings.max_models,
        inference_timeout=settings.inference_timeout,
        max_concurrent_sentences_per_model=settings.max_concurrent_sentences_per_model,
        engine_factory=factory,
        data_storage=storage,
    )
    hub = TtsEngineHub(
        frame_duration=settings.frame_duration,
        middlewares=[
            ResolveLanguageMiddleware().invoke,
            SplitSentencesMiddleware(
                max_sentence_chars=settings.max_sentence_chars,
                text_sentencizer_factory=TextSentencizerFactory(),
            ).invoke,
            NormalizeTextMiddleware(
                timeout=settings.normalization.timeout,
                max_concurrent_sentences=settings.normalization.max_concurrent_sentences_per_request,
                text_normalizer_factory=TextNormalizerFactory(
                    openai_client=None,
                    settings=settings.normalization,
                    storage=storage,
                ),
            ).invoke,
        ],
        engine_manager=engine_manager,
        data_storage=storage,
    )

    client = WyomingClient()
    handler = TtsEngineHubEventHandler(
        hub,
        storage,
        settings.app_name,
        supports_synthesize_streaming=settings.streaming,
        throw_detailed_errors=True,
        reader=client.reader,
        writer=client.writer,
    )

    try:
        events = []
        events += await client.send(
            handler, SynthesizeStart(voice=SynthesizeVoice(name=VOICE_ID)).event()
        )
        events += await client.send(handler, SynthesizeChunk(text=TEXT).event())
        events += await client.send(handler, SynthesizeStop().event())

        synthesized = [chunk for engine in factory.recordings for chunk in engine.synthesized]
        return StreamedRequest(synthesized=synthesized, events=events)
    finally:
        await engine_manager.close()


@pytest.fixture(scope="module")
def streamed() -> StreamedRequest:
    """One real synthesis, captured once for every assertion in this module."""
    if cached_model_path() is None or not published_sample_rates():
        pytest.skip(f"no cached Model at {MODELS_DIR / 'silero' / LANGUAGE / f'{MODEL_ID}.pt'}")

    with blocking_downloads() as downloads:
        result = asyncio.run(synthesize_and_read(make_settings()))

    reached_out = [name for name, patch in downloads.items() if patch.called]
    if reached_out:
        pytest.fail(f"the check reached for the network via {reached_out}")

    return result


class TestRealModelStream:
    """A real Model's audio reaches a client unchanged."""

    def test_client_receives_the_audio_the_model_synthesized(self, streamed):
        """The bytes on the wire are the audio the Model produced, byte for byte."""
        assert streamed.synthesized, "expected the Model to synthesize at least one Chunk"

        assert streamed_audio_bytes(streamed.events) == synthesized_bytes(streamed.synthesized)

    def test_client_hears_speech_rather_than_silence(self, streamed):
        """The streamed audio carries speech, so the comparison above is of real audio."""
        received = streamed.received

        assert received.size > 0
        assert np.abs(received).max() >= MIN_PEAK_AMPLITUDE

    def test_streamed_bytes_are_the_announced_format_for_that_duration(self, streamed):
        """The bytes streamed equal rate x duration x width x channels, as announced."""
        audio_format = streamed.format

        assert len(streamed_audio_bytes(streamed.events)) == round(
            audio_format.rate
            * streamed.synthesized_seconds
            * audio_format.width
            * audio_format.channels
        )

    def test_the_model_streams_at_the_rate_it_synthesized_at(self, streamed):
        """The rate a client is told is the rate the Model synthesized at, and publishes."""
        assert {chunk.sample_rate for chunk in streamed.synthesized} == {CONFIGURED_SAMPLE_RATE}
        assert streamed.format.rate == CONFIGURED_SAMPLE_RATE
        assert streamed.format.rate in published_sample_rates()

    def test_the_model_streams_at_the_format_silero_produces(self, streamed):
        """The audio is 16-bit mono, and every chunk agrees with the format announced."""
        assert (streamed.format.width, streamed.format.channels) == (
            EXPECTED_WIDTH,
            EXPECTED_CHANNELS,
        )
        assert audio_formats(streamed.events) == {streamed.format}
