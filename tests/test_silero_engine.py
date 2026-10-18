import contextlib
import os
import textwrap
import unittest.mock

import pytest
import torch

from src.config import Settings
from src.tts.engine_factory import TtsEngineFactory
from src.tts.models import BackendType, EngineType, ModelInfo, TextFormat
from src.tts.silero_engine import SileroTtsEngine
from tests.helpers import make_captured_silero_model, make_voice


def make_models_dir(tmp_path, registry_yaml, model_files):
    """Create a models dir with a custom registry and pre-placed .pt files.

    registry_yaml: the body of the registry after the `tts_models:` key.
    model_files: dict mapping a registry section to a list of model ids whose
    .pt files should be pre-placed under {section}/{model_id}.pt.
    """
    silero_dir = tmp_path / "models" / "silero"
    silero_dir.mkdir(parents=True)
    (silero_dir / "models.yml").write_text(textwrap.dedent(f"tts_models:\n{registry_yaml}\n"))
    for section, model_ids in model_files.items():
        section_dir = silero_dir / section
        section_dir.mkdir()
        for model_id in model_ids:
            (section_dir / f"{model_id}.pt").write_bytes(b"fake model")
    return str(tmp_path / "models")


def make_engine(
    tmp_path,
    registry_yaml,
    model_files,
    *,
    sample_rate=48000,
    device="cpu",
    model_id="unused",
    languages=None,
    models_dir=None,
):
    """Build a Silero TTS Engine over a models directory of the given shape.

    `models_dir` defaults to the directory `make_models_dir` just populated. Pass one
    to hold the engine to a directory other than the one the fixture wrote to — which
    is how a test puts the engine on the configured default.
    """
    built_dir = make_models_dir(tmp_path, registry_yaml, model_files)
    return SileroTtsEngine(
        model_info=ModelInfo(id=model_id, engine_type=EngineType.SILERO, languages=languages or []),
        device=device,
        sample_rate=sample_rate,
        models_dir=built_dir if models_dir is None else models_dir,
        models_yml_url="https://example.com/models.yml",
        models_yml_hash=None,
    )


def registry_with_rates(sample_rates):
    """Registry body declaring a single Silero Model publishing `sample_rates`."""
    return f"""
      ru:
        v5_5_ru:
          latest:
            package: 'http://example/v5_5_ru.pt'
            sample_rate: [{", ".join(str(rate) for rate in sample_rates)}]
    """


@contextlib.contextmanager
def loaded_silero_model():
    """Patch Silero's PackageImporter so warmup loads a CapturedSileroModel."""
    model, importer = make_captured_silero_model()
    with unittest.mock.patch(
        "src.tts.silero_engine.torch.package.PackageImporter", return_value=importer
    ):
        yield model


async def synthesize_with(engine, model, text="hello", model_id="v5_5_ru"):
    """Synthesize `text` through `engine` and return the yielded TtsResults."""
    voice = make_voice(voice_id=f"ru_RU-{model_id}-aidar", name="aidar", model=model_id)
    return [result async for result in engine.synthesize_pcm(text, voice, TextFormat.TEXT)]


class TestResolveModelSection:
    def test_single_language_model_info_resolves_from_declared_section(self, tmp_path):
        """A single-language Model Info whose id sits in its declared section resolves to it."""
        registry = """
          en:
            v3_en:
              latest:
                package: 'http://example/v3_en.pt'
                sample_rate: [8000, 24000, 48000]
                example: 'Hello'
                speakers:
                  en_0:
                    example: 'Hello from en_0'
        """
        engine = make_engine(tmp_path, registry, {"en": ["v3_en"]})
        model_info = ModelInfo(id="v3_en", engine_type=EngineType.SILERO, languages=["en"])

        model_path, sample_rates, example_text, speakers = engine._resolve_model_metadata(
            model_info
        )

        assert model_path.endswith(os.path.join("en", "v3_en.pt"))
        assert sample_rates == [8000, 24000, 48000]
        assert example_text == "Hello"
        assert speakers == {"en_0": "Hello from en_0"}

    def test_model_id_under_non_language_section_resolves_by_scan(self, tmp_path):
        """A model id listed under a non-language section (e.g. cyrillic) resolves by
        scanning even when the Model Info's declared Language does not match."""
        registry = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
          cyrillic:
            v4_cyrillic:
              latest:
                package: 'http://example/v4_cyrillic.pt'
                sample_rate: [8000, 24000, 48000]
                example: 'Пример'
        """
        engine = make_engine(tmp_path, registry, {"cyrillic": ["v4_cyrillic"]})
        model_info = ModelInfo(id="v4_cyrillic", engine_type=EngineType.SILERO, languages=["ru"])

        model_path, sample_rates, _, _ = engine._resolve_model_metadata(model_info)

        assert model_path.endswith(os.path.join("cyrillic", "v4_cyrillic.pt"))
        assert sample_rates == [8000, 24000, 48000]

    def test_multi_language_model_info_resolves_to_matching_section(self, tmp_path):
        """A multi-language Model Info resolves to the first registry section owning its id."""
        registry = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
          multi:
            multi_v2:
              latest:
                package: 'http://example/multi_v2.pt'
                sample_rate: [8000, 16000]
                speakers:
                  aidar:
                    lang: 'ru'
                    example: 'Привет'
        """
        engine = make_engine(tmp_path, registry, {"multi": ["multi_v2"]})
        model_info = ModelInfo(id="multi_v2", engine_type=EngineType.SILERO, languages=["ru", "en"])

        model_path, sample_rates, _, speakers = engine._resolve_model_metadata(model_info)

        assert model_path.endswith(os.path.join("multi", "multi_v2.pt"))
        assert sample_rates == [8000, 16000]
        assert speakers == {"aidar": "Привет"}

    def test_model_id_absent_from_registry_raises_clear_error(self, tmp_path):
        """A Model Info whose id is in no registry section raises a RuntimeError naming
        that id and the registry file it was looked up in."""
        registry = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
        """
        engine = make_engine(tmp_path, registry, {"ru": ["v5_5_ru"]})
        model_info = ModelInfo(id="v4_indic", engine_type=EngineType.SILERO, languages=["en"])

        with pytest.raises(RuntimeError) as exc_info:
            engine._resolve_model_metadata(model_info)

        message = str(exc_info.value)
        assert "v4_indic" in message
        assert os.path.join("silero", "models.yml") in message

    def test_model_id_without_stored_file_downloads_into_resolved_section(self, tmp_path):
        """A model id with no .pt file stored locally downloads into its section directory."""
        registry = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
          cyrillic:
            v4_cyrillic:
              latest:
                package: 'http://example/v4_cyrillic.pt'
                sample_rate: [8000, 24000, 48000]
                example: 'Пример'
        """
        engine = make_engine(tmp_path, registry, {})
        model_info = ModelInfo(id="v4_cyrillic", engine_type=EngineType.SILERO, languages=["ru"])

        with unittest.mock.patch(
            "src.tts.silero_engine.torch.hub.download_url_to_file"
        ) as mock_download:
            model_path, sample_rates, example_text, _ = engine._resolve_model_metadata(model_info)

        mock_download.assert_called_once()
        call = mock_download.call_args
        download_url = call.args[0]
        download_path = call.args[1]
        assert download_url == "http://example/v4_cyrillic.pt"
        assert download_path.endswith(os.path.join("cyrillic", "v4_cyrillic.pt"))
        assert model_path.endswith(os.path.join("cyrillic", "v4_cyrillic.pt"))
        assert sample_rates == [8000, 24000, 48000]
        assert example_text == "Пример"

    def test_resolution_uses_constructor_models_dir_not_config_object(self, tmp_path):
        """Resolution routes models_dir from the constructor — the engine has no `config`
        object and must not crash before the lookup runs."""
        registry = """
          en:
            v3_en:
              latest:
                package: 'http://example/v3_en.pt'
                sample_rate: [48000]
        """
        engine = make_engine(tmp_path, registry, {"en": ["v3_en"]})
        model_info = ModelInfo(id="v3_en", engine_type=EngineType.SILERO, languages=["en"])

        assert not hasattr(engine, "_config")
        model_path, _, _, _ = engine._resolve_model_metadata(model_info)

        assert model_path.endswith(os.path.join("en", "v3_en.pt"))


@pytest.mark.asyncio
class TestSampleRateSelection:
    """The TTS Engine synthesizes at the nearest Sample Rate the Model publishes."""

    @pytest.mark.parametrize(
        ("model_rates", "configured_rate", "expected_rate"),
        [
            pytest.param([8000, 24000], 48000, 24000, id="above-max-clamps-down"),
            pytest.param([24000, 48000], 8000, 24000, id="below-min-clamps-up"),
            pytest.param([24000, 48000], 44100, 24000, id="between-rates-highest-below"),
            pytest.param([24000, 48000], 48000, 48000, id="exact-match-used-as-is"),
            pytest.param([8000], 48000, 8000, id="single-rate-wins-over-config"),
            pytest.param([8000], 16000, 8000, id="single-rate-wins-over-low-config"),
            pytest.param([], 44100, 44100, id="no-published-rates-uses-config"),
        ],
    )
    async def test_synthesizes_at_nearest_published_rate(
        self, tmp_path, model_rates, configured_rate, expected_rate
    ):
        engine = make_engine(
            tmp_path,
            registry_with_rates(model_rates),
            {"ru": ["v5_5_ru"]},
            sample_rate=configured_rate,
            model_id="v5_5_ru",
        )

        with loaded_silero_model() as model:
            results = await synthesize_with(engine, model)

        assert model.requested_rates == [expected_rate]
        assert len(results) == 1
        assert results[0].sample_rate == expected_rate
        assert len(results[0].audio) == expected_rate


@pytest.mark.asyncio
class TestDeviceFallback:
    """An unavailable compute device falls back to CPU rather than failing."""

    @pytest.mark.parametrize(
        ("device", "device_namespace"),
        [
            pytest.param("cuda", "cuda", id="cuda-requested"),
            pytest.param("xpu", "xpu", id="xpu-requested"),
        ],
    )
    async def test_unavailable_device_falls_back_to_cpu(self, tmp_path, device, device_namespace):
        """An unavailable device is probed, rejected, and the TTS Engine lands on CPU."""
        engine = make_engine(
            tmp_path,
            registry_with_rates([48000]),
            {"ru": ["v5_5_ru"]},
            device=device,
            model_id="v5_5_ru",
        )
        unavailable_device = unittest.mock.MagicMock()
        unavailable_device.is_available.return_value = False

        with (
            loaded_silero_model() as model,
            unittest.mock.patch.object(torch, device_namespace, unavailable_device, create=True),
        ):
            results = await synthesize_with(engine, model)

        unavailable_device.is_available.assert_called()
        assert engine.device == torch.device("cpu")
        assert model.requested_devices == [torch.device("cpu")]
        assert len(results) == 1
        assert results[0].sample_rate == 48000
        assert results[0].bytes_per_sample == 2
        assert results[0].channels == 1


class TestDefaultModelsDirectory:
    """The default directory is the one the TTS Engine lays its models out under."""

    REGISTRY = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
                sample_rate: [48000]
        """

    def test_the_default_directory_holds_the_engine_layout(self, tmp_path, monkeypatch):
        """With nothing configured, a stored model is found where the layout says.

        The engine puts its registry and weights under `silero/` inside models_dir, so
        models_dir is the parent of that directory rather than the directory itself — a
        default naming `silero` as well would have the engine look one level too deep,
        find nothing, and re-download on every start.
        """
        monkeypatch.chdir(tmp_path)
        engine = make_engine(
            tmp_path,
            self.REGISTRY,
            {"ru": ["v5_5_ru"]},
            model_id="v5_5_ru",
            languages=["ru"],
            models_dir=Settings().models_dir,
        )

        model_path, _, _, _ = engine._resolve_model_metadata(engine.model_info)

        assert model_path == os.path.join("models", "silero", "ru", "v5_5_ru.pt")

    def test_a_model_missing_from_the_default_directory_downloads_there(
        self, tmp_path, monkeypatch
    ):
        """An uncached model lands under the default directory, not one level deeper."""
        monkeypatch.chdir(tmp_path)
        engine = make_engine(
            tmp_path,
            self.REGISTRY,
            {},
            model_id="v5_5_ru",
            languages=["ru"],
            models_dir=Settings().models_dir,
        )

        with unittest.mock.patch(
            "src.tts.silero_engine.torch.hub.download_url_to_file"
        ) as download:
            model_path, _, _, _ = engine._resolve_model_metadata(engine.model_info)

        download.assert_called_once()
        assert download.call_args.args[1] == os.path.join("models", "silero", "ru", "v5_5_ru.pt")
        assert model_path == os.path.join("models", "silero", "ru", "v5_5_ru.pt")

    def test_the_engine_factory_hands_the_engine_that_directory(self):
        """The default reaches the engine through the wiring that builds it.

        Resolving against a default read straight from Settings would still pass if the
        Engine Factory routed some other directory to the TTS Engine.
        """
        settings = Settings()
        engine = TtsEngineFactory(settings=settings).create(
            ModelInfo(id="v5_5_ru", engine_type=EngineType.SILERO), BackendType.TORCH
        )

        assert engine._models_dir == settings.models_dir == "models"
