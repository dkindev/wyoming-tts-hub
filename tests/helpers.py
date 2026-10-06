import contextlib
import hashlib
import os
import unittest.mock

import numpy as np
import torch
import yaml

from src.tts.data_storage import DataStorage
from src.tts.engine import TtsEngine
from src.tts.models import EngineType, Model, TextFormat, TtsResult, Voice


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
    ssml_supported=False,
    warmup=False,
    enabled=True,
):
    return Model(
        id=id,
        engine_type=engine_type,
        languages=languages if languages is not None else [],
        ssml_supported=ssml_supported,
        warmup=warmup,
        enabled=enabled,
    )


def make_merged_yaml(tmp_path, models_data: dict) -> str:
    """Write a merged-structure config YAML and return its path."""
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(yaml.dump({"models": models_data}))
    return str(config_yml)


async def collect_hub_sentences(hub, text, voice_id, input_type=TextFormat.TEXT):
    """Collect all TtsResult chunks yielded by the Engine Hub's synthesize_pcm_chunks."""
    return [chunk async for chunk in hub.synthesize_pcm_chunks(text, voice_id, input_type)]


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
    """

    def __init__(
        self, model: Model, *, sample_rate: int = 48000, samples_per_sentence: int = 48000
    ):
        super().__init__(model)
        self.sample_rate = sample_rate
        self.samples_per_sentence = samples_per_sentence
        self.requests: list[tuple[str, Voice, TextFormat, str | None]] = []

    @property
    def synthesized_texts(self) -> list[str]:
        """The text of every sentence this engine was asked to synthesize."""
        return [text for text, _, _, _ in self.requests]

    @property
    def audio_size_bytes(self) -> int:
        """Total audio bytes this engine emits per sentence, at 2 bytes per sample."""
        return self.samples_per_sentence * 2

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
        yield TtsResult(
            audio=np.zeros(self.samples_per_sentence, dtype=np.int16),
            sample_rate=self.sample_rate,
            bytes_per_sample=2,
            channels=1,
        )


class FakeDataStorage(DataStorage):
    """A DataStorage that returns exactly the Models and Voices it is given.

    Unlike YamlDataStorage it does not filter a Voice away when its Model is
    absent, so Hub-side guards for that case can be exercised.
    """

    def __init__(self, models=None, voices=None):
        self._models = {model.id: model for model in models or []}
        self._voices = {voice.id: voice for voice in voices or []}

    def get_voices(self) -> list[Voice]:
        return list(self._voices.values())

    def get_voice(self, voice_id: str) -> Voice | None:
        return self._voices.get(voice_id)

    def get_model(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    def get_models(self) -> list[Model]:
        return list(self._models.values())

    def get_prompt(self, prompt_id: str):
        return None

    def get_voice_normalization(self, voice_id: str, text_format: TextFormat, language: str):
        return None


class FakeEngineManager:
    """An Engine Manager that hands out pre-built engines keyed by Model id."""

    def __init__(self, engines: dict[str, TtsEngine] | None = None):
        self._engines = engines or {}
        self.requested_model_ids: list[str] = []

    async def get_context(self, model_id: str):
        self.requested_model_ids.append(model_id)
        engine = self._engines.get(model_id)
        if engine is None:
            return None

        @contextlib.asynccontextmanager
        async def acquire():
            yield engine

        return acquire()
