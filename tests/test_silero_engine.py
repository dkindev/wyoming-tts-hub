import os
import textwrap
import unittest.mock

import pytest

from src.tts.exceptions import TTSEngineError
from src.tts.models import EngineType, Model
from src.tts.silero_engine import SileroTtsEngine


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


def make_engine(tmp_path, registry_yaml, model_files):
    models_dir = make_models_dir(tmp_path, registry_yaml, model_files)
    return SileroTtsEngine(
        model=Model(id="unused", engine_type=EngineType.SILERO),
        device="cpu",
        sample_rate=48000,
        models_dir=models_dir,
        models_yml_url="https://example.com/models.yml",
        models_yml_hash=None,
    )


class TestResolveModelSection:
    def test_single_language_model_resolves_from_declared_section(self, tmp_path):
        """A single-language Model present in its declared registry section resolves to it."""
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
        model = Model(id="v3_en", engine_type=EngineType.SILERO, languages=["en"])

        model_path, sample_rates, example_text, speakers = engine._resolve_model_metadata(model)

        assert model_path.endswith(os.path.join("en", "v3_en.pt"))
        assert sample_rates == [8000, 24000, 48000]
        assert example_text == "Hello"
        assert speakers == {"en_0": "Hello from en_0"}

    def test_model_under_non_language_section_resolves_by_scan(self, tmp_path):
        """A Model living under a non-language section (e.g. cyrillic) resolves by scanning
        even when its declared single Language does not match."""
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
        model = Model(id="v4_cyrillic", engine_type=EngineType.SILERO, languages=["ru"])

        model_path, sample_rates, _, _ = engine._resolve_model_metadata(model)

        assert model_path.endswith(os.path.join("cyrillic", "v4_cyrillic.pt"))
        assert sample_rates == [8000, 24000, 48000]

    def test_multi_language_model_resolves_to_matching_section(self, tmp_path):
        """A multi-language Model resolves to the first registry section that owns it."""
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
        model = Model(id="multi_v2", engine_type=EngineType.SILERO, languages=["ru", "en"])

        model_path, sample_rates, _, speakers = engine._resolve_model_metadata(model)

        assert model_path.endswith(os.path.join("multi", "multi_v2.pt"))
        assert sample_rates == [8000, 16000]
        assert speakers == {"aidar": "Привет"}

    def test_model_absent_from_registry_raises_clear_error(self, tmp_path):
        """A Model present in no registry section raises a TTSEngineError naming the model
        and pointing at the cached models.yml."""
        registry = """
          ru:
            v5_5_ru:
              latest:
                package: 'http://example/v5_5_ru.pt'
        """
        engine = make_engine(tmp_path, registry, {"ru": ["v5_5_ru"]})
        model = Model(id="v4_indic", engine_type=EngineType.SILERO, languages=["en"])

        with pytest.raises(TTSEngineError) as exc_info:
            engine._resolve_model_metadata(model)

        message = str(exc_info.value)
        assert "v4_indic" in message
        assert "models.yml" in message

    def test_model_without_local_file_downloads_into_resolved_section(self, tmp_path):
        """A Model not stored locally is downloaded into the resolved section directory."""
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
        model = Model(id="v4_cyrillic", engine_type=EngineType.SILERO, languages=["ru"])

        with unittest.mock.patch(
            "src.tts.silero_engine.torch.hub.download_url_to_file"
        ) as mock_download:
            model_path, sample_rates, example_text, _ = engine._resolve_model_metadata(model)

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
        model = Model(id="v3_en", engine_type=EngineType.SILERO, languages=["en"])

        assert not hasattr(engine, "_config")
        model_path, _, _, _ = engine._resolve_model_metadata(model)

        assert model_path.endswith(os.path.join("en", "v3_en.pt"))
