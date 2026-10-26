import unittest.mock

import pytest
import torch

from src.config import Settings
from src.tts.engine_factory import TtsEngineFactory
from src.tts.models import BackendType, EngineType, TextFormat
from src.tts.qwen_engine import QwenTtsEngine
from src.tts.silero_engine import SileroTtsEngine
from tests.helpers import (
    make_captured_silero_model,
    make_model_info,
    make_models_dir,
    make_voice,
)

MODEL_ID = "v5_6_ru"
VOICE_ID = "ru_RU-v5_6_ru-aidar"
REGISTRY_URL = "https://example.com/registry.yml"


def make_settings(
    tmp_path,
    monkeypatch,
    *,
    models_dir=None,
    device="cpu",
    sample_rate=48000,
    registry_url=REGISTRY_URL,
    registry_hash="",
):
    """Return Settings carrying only what this test asks for.

    Every source Settings reads is pinned here — the environment, the dotenv file
    and the config file — so the factory under test sees the values below and
    nothing from the developer's checkout.
    """
    monkeypatch.setenv("TTS_CONFIG_PATH", str(tmp_path / "absent-config.yml"))
    monkeypatch.setenv("TTS_MODELS_DIR", models_dir or str(tmp_path / "models"))
    monkeypatch.setenv("TTS_TORCH__DEVICE", device)
    monkeypatch.setenv("TTS_SILERO__SAMPLE_RATE", str(sample_rate))
    monkeypatch.setenv("TTS_SILERO__MODELS_YML_URL", registry_url)
    monkeypatch.setenv("TTS_SILERO__MODELS_YML_HASH", registry_hash)

    return Settings(active_models=[MODEL_ID], _env_file=None)


def build_engine(tmp_path, monkeypatch, *, model=MODEL_ID, engine_type=EngineType.SILERO, **config):
    """Return the TTS Engine the factory builds for `model` under the given settings."""
    settings = make_settings(tmp_path, monkeypatch, **config)
    return TtsEngineFactory(settings=settings).create(
        make_model_info(id=model, engine_type=engine_type), BackendType.TORCH
    )


async def synthesize(engine, model_id=MODEL_ID):
    """Synthesize through `engine` and return the yielded TtsResults."""
    voice = make_voice(voice_id=VOICE_ID, name="aidar", model=model_id)
    return [result async for result in engine.synthesize_pcm("Привет", voice, TextFormat.TEXT)]


class TestEngineResolution:
    """A Model Info declares its TTS Engine family; the factory resolves it to an engine."""

    def test_silero_model_info_on_torch_backend_yields_silero_engine(self, tmp_path, monkeypatch):
        """A Silero Model Info on the torch backend is built as a Silero TTS Engine."""
        engine = build_engine(tmp_path, monkeypatch)

        assert isinstance(engine, SileroTtsEngine)
        assert engine.model_info.id == MODEL_ID

    def test_qwen3_model_info_on_torch_backend_yields_qwen3_engine(self, tmp_path, monkeypatch):
        """A qwen3 Model Info on the torch backend is built as a Qwen3-TTS Engine."""
        engine = build_engine(
            tmp_path,
            monkeypatch,
            model=MODEL_ID,
            engine_type=EngineType.QWEN3,
        )

        assert isinstance(engine, QwenTtsEngine)
        assert engine.model_info.id == MODEL_ID

    def test_declared_but_unimplemented_family_is_rejected(self, tmp_path, monkeypatch):
        """A family declared in the domain vocabulary with no engine behind it is rejected by name."""
        settings = make_settings(tmp_path, monkeypatch)
        factory = TtsEngineFactory(settings=settings)
        engine_type = EngineType.OPENAI

        with pytest.raises(ValueError) as exc_info:
            factory.create(
                make_model_info(id="whatever", engine_type=engine_type), BackendType.TORCH
            )

        assert engine_type.value in str(exc_info.value)
        assert BackendType.TORCH.value in str(exc_info.value)

    def test_missing_model_info_is_a_type_error(self, tmp_path, monkeypatch):
        """Asking for an engine without a Model Info fails at the seam, not inside a family."""
        settings = make_settings(tmp_path, monkeypatch)
        factory = TtsEngineFactory(settings=settings)

        with pytest.raises(TypeError):
            factory.create(None, BackendType.TORCH)


@pytest.mark.asyncio
class TestEngineConfiguration:
    """The constructed TTS Engine is configured from the server settings."""

    async def test_engine_infers_from_configured_models_dir_and_sample_rate(
        self, tmp_path, monkeypatch
    ):
        """The configured models directory and sample rate decide what the engine infers."""
        models_dir = make_models_dir(tmp_path, sample_rates=[16000, 48000])
        engine = build_engine(tmp_path, monkeypatch, models_dir=models_dir, sample_rate=24000)
        loaded_model, importer = make_captured_silero_model()

        with unittest.mock.patch(
            "src.tts.silero_engine.torch.package.PackageImporter", return_value=importer
        ):
            results = await synthesize(engine)

        assert loaded_model.requested_rates == [16000]
        assert results[0].sample_rate == 16000
        assert len(results[0].audio) == 16000

    async def test_engine_runs_on_configured_device(self, tmp_path, monkeypatch):
        """The configured device is the one the engine asks the loaded model to move to."""
        engine = build_engine(
            tmp_path,
            monkeypatch,
            models_dir=make_models_dir(tmp_path),
            device="cuda",
        )
        loaded_model, importer = make_captured_silero_model()
        available_cuda = unittest.mock.MagicMock()
        available_cuda.is_available.return_value = True

        with (
            unittest.mock.patch(
                "src.tts.silero_engine.torch.package.PackageImporter", return_value=importer
            ),
            unittest.mock.patch.object(torch, "cuda", available_cuda),
        ):
            await engine.warmup()

        assert engine.device == torch.device("cuda")
        assert loaded_model.requested_devices == [torch.device("cuda")]

    async def test_engine_fetches_configured_registry_url_when_none_is_stored(
        self, tmp_path, monkeypatch
    ):
        """With no registry stored locally, the engine downloads the configured registry URL."""
        (tmp_path / "models" / "silero").mkdir(parents=True)
        engine = build_engine(tmp_path, monkeypatch)

        with unittest.mock.patch("src.tts.silero_engine.urllib.request.urlretrieve") as urlretrieve:
            with pytest.raises(RuntimeError):
                await engine.warmup()

        urlretrieve.assert_called_once()
        assert urlretrieve.call_args.args[0] == REGISTRY_URL
