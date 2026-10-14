import asyncio
import hashlib
import io
import os
import unittest.mock

import numpy as np
import torch
import yaml
from wyoming.event import Event, read_event

from src.tts.data_storage import DataStorage
from src.tts.engine import TtsEngine
from src.tts.engine_hub import TtsEngineHub
from src.tts.models import (
    BackendType,
    EngineType,
    Model,
    Prompt,
    TextFormat,
    TtsResult,
    Voice,
    VoiceNormalization,
)


def hash_models_yml(yml_path: str) -> str:
    """Compute SHA256 hex digest of a models.yml file."""
    hasher = hashlib.sha256()
    with open(yml_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def models_yml_path(models_dir: str) -> str:
    """Return the path to models.yml within the silero subdirectory."""
    return os.path.join(models_dir, "silero", "models.yml")


def make_models_dir(
    tmp_path,
    sample_rates=None,
    model_name="v5_5_ru",
    language="ru",
    yml_content=None,
    pt_content=b"fake model",
):
    """Create a models directory with pre-populated models.yml and .pt files.

    Args:
        tmp_path: Temporary path root (from pytest tmp_path fixture).
        sample_rates: List of sample rates for the model. Defaults to [48000].
        model_name: Name of the model. Defaults to "v5_5_ru".
        language: Language code. Defaults to "ru".
        yml_content: Optional custom models.yml content as bytes. When provided,
            replaces the auto-generated YAML with this content and uses the
            default model_name/language in the path.
        pt_content: Optional model .pt file content. Defaults to b"fake model".

    Returns:
        The models_dir path (str), with models.yml at {models_dir}/silero/models.yml
        and the model .pt file at {models_dir}/silero/{language}/{model_name}.pt.
    """
    if sample_rates is None:
        sample_rates = [48000]
    rates_str = ", ".join(str(r) for r in sample_rates)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    silero_dir = models_dir / "silero"
    silero_dir.mkdir()
    if yml_content is not None:
        (silero_dir / "models.yml").write_bytes(yml_content)
    else:
        yml = (
            f"tts_models:\n  {language}:\n    {model_name}:\n"
            f"      latest:\n"
            f"        package: 'http://x'\n"
            f"        sample_rate: [{rates_str}]\n"
        )
        (silero_dir / "models.yml").write_text(yml)
    lang_dir = silero_dir / language
    lang_dir.mkdir()
    (lang_dir / f"{model_name}.pt").write_bytes(pt_content)
    return str(models_dir)


def make_config_file(tmp_path, models=None):
    """Create a temp config file with merged structure."""
    config_yml = tmp_path / "config.yml"
    config_data = {"models": models or {}}
    config_yml.write_text(yaml.dump(config_data))
    return str(config_yml)


def make_voice(*, voice_id, name, speaker=None, model="v5_5_ru"):
    return Voice(
        id=voice_id,
        name=name,
        speaker=speaker or name,
        model_id=model,
    )


def make_model(
    id="v5_5_ru",
    engine_type=EngineType.SILERO,
    languages=None,
    language_auto_detected=False,
    ssml_supported=False,
    warmup=False,
    enabled=True,
):
    return Model(
        id=id,
        engine_type=engine_type,
        languages=languages if languages is not None else [],
        language_auto_detected=language_auto_detected,
        ssml_supported=ssml_supported,
        warmup=warmup,
        enabled=enabled,
    )


def make_merged_yaml(tmp_path, models_data: dict) -> str:
    """Write a merged-structure config YAML and return its path."""
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(yaml.dump({"models": models_data}))
    return str(config_yml)


async def collect_hub_sentences(hub, text, voice_id, input_type=TextFormat.TEXT, language=None):
    """Collect all TtsResult chunks yielded by the Engine Hub's synthesize_pcm_chunks."""
    return [
        chunk async for chunk in hub.synthesize_pcm_chunks(text, voice_id, input_type, language)
    ]


class CapturedSileroModel:
    """Stand-in for a loaded Silero package that records the rates it was asked for.

    `apply_tts` returns one second of audio at the requested rate, so a caller can
    check both the rate the TTS Engine selected and that audio of that rate came back.
    """

    def __init__(self):
        self.requested_rates: list[int] = []
        self.requested_devices: list[torch.device] = []

    def apply_tts(self, *, text, speaker, sample_rate):
        self.requested_rates.append(sample_rate)
        return torch.zeros(1, sample_rate)

    def to(self, device):
        self.requested_devices.append(device)
        return self


def make_captured_silero_model() -> CapturedSileroModel:
    """Return a CapturedSileroModel plus a PackageImporter patch that yields it."""
    model = CapturedSileroModel()

    importer = unittest.mock.MagicMock()
    importer.load_pickle.return_value = model

    return model, importer


class FakeTtsEngine(TtsEngine):
    """A TTS Engine that yields canned audio instead of inferring it.

    Every synthesized sentence produces one chunk of `samples_per_sentence` audio,
    so callers can ask the fake what it emitted rather than restating the numbers.
    Counts warmups and closes so lifecycle tests can assert on them. When `hold` is
    given, synthesis blocks on it, letting a test observe concurrency from outside.
    """

    def __init__(
        self,
        model: Model,
        *,
        sample_rate: int = 48000,
        samples_per_sentence: int = 48000,
        warmup_error: Exception | None = None,
        hold: asyncio.Event | None = None,
    ):
        super().__init__(model)
        self.sample_rate = sample_rate
        self.samples_per_sentence = samples_per_sentence
        self.warmup_error = warmup_error
        self.warmup_count = 0
        self.close_count = 0
        self.requests: list[tuple[str, Voice, TextFormat, str | None]] = []
        self.active_syntheses = 0
        self.peak_syntheses = 0
        self._hold = hold

    @property
    def synthesized_texts(self) -> list[str]:
        """The text of every sentence this engine was asked to synthesize."""
        return [text for text, _, _, _ in self.requests]

    @property
    def languages(self) -> list[str | None]:
        """The Language of every request this engine was asked to synthesize."""
        return [language for _, _, _, language in self.requests]

    @property
    def audio_size_bytes(self) -> int:
        """Total audio bytes this engine emits per sentence, at 2 bytes per sample."""
        return self.samples_per_sentence * 2

    async def warmup(self) -> None:
        self.warmup_count += 1
        if self.warmup_error is not None:
            raise self.warmup_error
        await super().warmup()

    async def close(self) -> None:
        self.close_count += 1
        await super().close()

    async def _warmup(self) -> bool:
        return True

    async def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ):
        self.requests.append((text, voice, text_format, language))
        self.active_syntheses += 1
        self.peak_syntheses = max(self.peak_syntheses, self.active_syntheses)
        try:
            if self._hold is not None:
                await self._hold.wait()
            yield TtsResult(
                audio=np.zeros(self.samples_per_sentence, dtype=np.int16),
                sample_rate=self.sample_rate,
                bytes_per_sample=2,
                channels=1,
            )
        finally:
            self.active_syntheses -= 1


class FakeEngineFactory:
    """An Engine Factory that builds FakeTtsEngines and records what it was asked for.

    `engines` maps a Model id to the engine to hand back, so a test can watch one
    engine through its lifecycle. Model ids absent from it get a fresh FakeTtsEngine.
    """

    def __init__(self, engines: dict[str, FakeTtsEngine] | None = None):
        self._engines = dict(engines or {})
        self.requested_model_ids: list[str] = []

    def create(self, model: Model, backend_type: BackendType) -> TtsEngine:
        self.requested_model_ids.append(model.id)
        if model.id not in self._engines:
            self._engines[model.id] = FakeTtsEngine(model)
        return self._engines[model.id]


class _MemoryTransport(asyncio.WriteTransport):
    """A write transport that keeps every byte written to it instead of sending it."""

    def __init__(self):
        super().__init__()
        self.data = bytearray()
        self._closing = False

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.data.extend(data)

    def close(self) -> None:
        self._closing = True

    def is_closing(self) -> bool:
        return bool(self._closing)


class WyomingClient:
    """A Wyoming client talking to an event handler over an in-memory socket.

    `reader` and `writer` are the two ends the handler is constructed with;
    `written_events` parses back the bytes the handler wrote, the way a real
    client would read them off the wire. Must be built inside a running loop.
    """

    def __init__(self):
        self.reader = asyncio.StreamReader()
        self._transport = _MemoryTransport()
        self.writer = asyncio.StreamWriter(
            self._transport, asyncio.streams.FlowControlMixin(), None, asyncio.get_running_loop()
        )
        self._consumed = 0

    async def send(self, handler, *events: Event) -> list[Event]:
        """Hand each event to `handler`, then return the events it wrote back."""
        for event in events:
            assert await handler.handle_event(event)

        return self.written_events()

    def written_events(self) -> list[Event]:
        """Parse every event written so far that has not been read back yet."""
        stream = io.BytesIO(bytes(self._transport.data))
        stream.seek(self._consumed)

        events = []
        while (event := read_event(stream)) is not None:
            events.append(event)

        self._consumed = stream.tell()
        return events


class FakeDataStorage(DataStorage):
    """A DataStorage that returns exactly the Models and Voices it is given.

    Unlike YamlDataStorage it does not filter a Voice away when its Model is
    absent, so Hub-side guards for that case can be exercised.
    """

    def __init__(self, models=None, voices=None, voice_normalizations=None, prompts=None):
        self._models = {model.id: model for model in models or []}
        self._voices = {voice.id: voice for voice in voices or []}
        self._prompts = {prompt.id: prompt for prompt in prompts or []}
        self._voice_normalizations = {
            f"{vn.voice_id}__{vn.text_format.value}__{vn.language}": vn
            for vn in voice_normalizations or []
        }

    def get_voices(self) -> list[Voice]:
        return list(self._voices.values())

    def get_voice(self, voice_id: str) -> Voice | None:
        return self._voices.get(voice_id)

    def get_model(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    def get_models(self) -> list[Model]:
        return list(self._models.values())

    def get_prompt(self, prompt_id: str) -> Prompt | None:
        return self._prompts.get(prompt_id)

    def get_voice_normalization(
        self, voice_id: str, text_format: TextFormat, language: str
    ) -> VoiceNormalization | None:
        return self._voice_normalizations.get(f"{voice_id}__{text_format.value}__{language}")


def make_hub(*, engine, middlewares, storage, frame_duration=50, engine_manager=None):
    """Return a TTS Engine Hub wired to fakes around the given engine."""
    return TtsEngineHub(
        frame_duration=frame_duration,
        middlewares=list(middlewares),
        engine_manager=(
            engine_manager
            if engine_manager is not None
            else FakeEngineManager({engine.model.id: engine})
        ),
        data_storage=storage,
    )


class ReusableEngineContext:
    """A reentrant async context manager yielding one engine.

    The Hub enters the engine context once per sentence, and several sentences are
    in flight concurrently, so the context must support overlapping entries. A
    one-shot `@asynccontextmanager` cannot, hence this class.
    """

    def __init__(self, engine: TtsEngine):
        self._engine = engine

    async def __aenter__(self) -> TtsEngine:
        return self._engine

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False


class FakeEngineManager:
    """An Engine Manager that hands out pre-built engines keyed by Model id."""

    def __init__(self, engines: dict[str, TtsEngine] | None = None):
        self._engines = engines or {}
        self.requested_model_ids: list[str] = []

    async def get_context(self, model_id: str) -> ReusableEngineContext | None:
        self.requested_model_ids.append(model_id)
        engine = self._engines.get(model_id)
        return ReusableEngineContext(engine) if engine is not None else None
