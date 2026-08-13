import unittest.mock

import pytest
import torch

from src.tts.data_storage import YamlDataStorage
from src.tts.engine import BYTES_PER_SAMPLE, CHANNELS, SileroTTSEngine
from src.tts.exceptions import TTSEngineError
from src.tts.models import PredefinedData, TextFormat, TtsConfig, TtsResult
from src.tts.preprocessing import TextSentenizerFactory
from tests.helpers import (
    collect_sentences,
    hash_models_yml,
    make_config_file,
    make_model,
    make_models_dir,
    make_voice,
    models_yml_path,
)


class TestSileroTTSEngineInit:
    """Tests for SileroTTSEngine initialization."""

    @pytest.mark.asyncio
    async def test_engine_uses_models_yml_hash_from_config(self, tmp_path, mock_package_importer):
        """Engine reads models_yml_hash from TTSConfig for local file validation."""
        models_dir = make_models_dir(tmp_path)
        yml_path = models_yml_path(models_dir)
        actual_hash = hash_models_yml(yml_path)

        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=actual_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        with unittest.mock.patch(
            "src.tts.engine.urllib.request.urlopen",
            side_effect=RuntimeError("network disabled"),
        ):
            storage = YamlDataStorage(config_model)
            engine = SileroTTSEngine(
                config=config,
                storage=storage,
                text_sentenizer_factory=TextSentenizerFactory(),
                text_normalizer_factory=None,
            )
            results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert len(results) > 0
        for r in results:
            assert isinstance(r, TtsResult)
            assert isinstance(r.audio, bytes)
            assert r.bytes_per_sample == BYTES_PER_SAMPLE
            assert r.channels == CHANNELS

    @pytest.mark.asyncio
    async def test_init_accepts_config_path_and_loads_config(self, tmp_path, default_tts_config):
        """Engine should accept config_path string and load config internally."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    language: ru
    locales:
      ru_RU:
        voices:
          - name: aidar
            speaker: aidar
            model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        assert engine is not None
        assert engine.get_storage().get_voice("ru_RU-v5_5_ru-aidar") is not None

    @pytest.mark.asyncio
    async def test_init_caches_locales(self, tmp_path, default_tts_config):
        """Engine should cache voices at init time."""
        config_path = make_config_file(
            tmp_path,
            models={
                "v5_5_ru": {
                    "language": "ru",
                    "locales": {
                        "ru_RU": {
                            "language": "ru",
                            "voices": [
                                {
                                    "name": "aidar",
                                    "speaker": "aidar",
                                    "model": "v5_5_ru",
                                }
                            ],
                        }
                    },
                }
            },
        )

        storage = YamlDataStorage(config_path)
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        voices = engine.get_storage().get_voices()
        assert isinstance(voices, list)
        assert len(voices) == 1
        assert voices[0].locale == "ru_RU"
        assert voices[0].id == "ru_RU-v5_5_ru-aidar"


class TestGetInputTypes:
    """Tests for get_input_types() method."""

    @pytest.mark.asyncio
    async def test_get_input_types_returns_tuple(self, tmp_path, default_tts_config):
        """get_input_types should return a tuple."""
        config_path = make_config_file(tmp_path, models={})
        storage = YamlDataStorage(config_path)
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        result = engine.get_supported_text_formats()
        assert isinstance(result, tuple)

    @pytest.mark.asyncio
    async def test_get_input_types_includes_text_and_ssml(self, tmp_path, default_tts_config):
        """get_input_types should include TEXT and SSML."""
        config_path = make_config_file(tmp_path, models={})
        storage = YamlDataStorage(config_path)
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        result = engine.get_supported_text_formats()
        assert TextFormat.TEXT in result
        assert TextFormat.SSML in result
        assert len(result) == 2


class TestSynthesizeValidation:
    """Tests for synthesize_pcm_chunks() validation."""

    @pytest.mark.asyncio
    async def test_synthesize_invalid_voice_raises_error(
        self, tmp_path, default_tts_config, mock_package_importer
    ):
        """synthesize_pcm_chunks with invalid voice_id should raise TTSEngineError."""
        config_path = make_config_file(
            tmp_path,
            models={
                "v5_5_ru": {
                    "engine_type": "silero",
                    "languages": ["ru"],
                    "voices": [
                        {"name": "aidar", "speaker": "aidar"},
                    ],
                }
            },
        )

        storage = YamlDataStorage(config_path)
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        with pytest.raises(TTSEngineError) as exc_info:
            await collect_sentences(engine, "hello", "invalid_voice_id")

        assert "Unsupported voice: invalid_voice_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_synthesize_invalid_input_type_raises_error(
        self, tmp_path, default_tts_config, mock_package_importer
    ):
        """synthesize_pcm_chunks with invalid input_type should raise TTSEngineError."""
        config_path = make_config_file(
            tmp_path,
            models={
                "v5_5_ru": {
                    "engine_type": "silero",
                    "languages": ["ru"],
                    "voices": [
                        {"name": "aidar", "speaker": "aidar"},
                    ],
                }
            },
        )

        storage = YamlDataStorage(config_path)
        engine = SileroTTSEngine(
            config=default_tts_config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        with pytest.raises(TTSEngineError):
            async for _ in engine.synthesize_pcm_chunks("hello", "v5_5_ru-aidar", "INVALID"):
                pass

    @pytest.mark.asyncio
    async def test_synthesize_successful_returns_tts_results(self, tmp_path, mock_package_importer):
        """synthesize_pcm_chunks with valid params should yield TTSResult objects."""
        models_dir = make_models_dir(tmp_path, sample_rates=[48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert len(results) > 0
        r = results[0]
        assert isinstance(r, TtsResult)
        assert isinstance(r.audio, bytes)
        assert r.sample_rate == 48000
        assert r.bytes_per_sample == BYTES_PER_SAMPLE
        assert r.channels == CHANNELS

    @pytest.mark.asyncio
    async def test_synthesize_skips_hash_validation_when_config_hash_empty(
        self, tmp_path, mock_package_importer
    ):
        """synthesize_pcm_chunks should skip models.yml hash validation when models_yml_hash is empty."""
        models_dir = make_models_dir(tmp_path)
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com/models.yml",
            models_yml_hash="",
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        with unittest.mock.patch(
            "src.tts.engine.urllib.request.urlopen",
            side_effect=RuntimeError("network disabled"),
        ):
            storage = YamlDataStorage(config_model)
            engine = SileroTTSEngine(
                config=config,
                storage=storage,
                text_sentenizer_factory=TextSentenizerFactory(),
                text_normalizer_factory=None,
            )
            results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_clamped_to_model_max(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should clamp sample rate to model's max if configured rate exceeds it."""
        models_dir = make_models_dir(tmp_path, sample_rates=[8000, 24000])
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=yml_hash,
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 24000
        assert results[0].sample_rate == 24000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_below_min_uses_min(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use min available rate if configured rate is below min."""
        models_dir = make_models_dir(tmp_path, sample_rates=[24000, 48000])
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=8000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=yml_hash,
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 24000
        assert results[0].sample_rate == 24000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_exact_match_uses_config(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use config rate if it exactly matches available rate."""
        models_dir = make_models_dir(tmp_path, sample_rates=[24000, 48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=24000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 24000
        assert results[0].sample_rate == 24000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_not_in_list_uses_highest_below(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use highest available rate below config if config not in list."""
        models_dir = make_models_dir(tmp_path, sample_rates=[24000, 48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=44100,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 24000
        assert results[0].sample_rate == 24000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_single_element_uses_that_element(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use single available rate regardless of config value."""
        models_dir = make_models_dir(tmp_path, sample_rates=[24000])
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=yml_hash,
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 24000
        assert results[0].sample_rate == 24000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_empty_list_uses_config(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use config rate if model has no sample rates."""
        models_dir = make_models_dir(tmp_path, sample_rates=[])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 48000
        assert results[0].sample_rate == 48000

    @pytest.mark.asyncio
    async def test_synthesize_sample_rate_none_uses_config(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """synthesize_pcm_chunks should use config rate if model sample rates is None."""
        models_dir = make_models_dir(tmp_path, sample_rates=[])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=str(models_dir),
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        calls = []
        original_return = mock_model.apply_tts.return_value

        def capture_apply_tts(text, speaker, sample_rate):
            calls.append(sample_rate)
            return original_return

        mock_model.apply_tts = capture_apply_tts

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert calls[0] == 48000
        assert results[0].sample_rate == 48000

    @pytest.mark.asyncio
    async def test_synthesize_lazy_model_loading(self, tmp_path, mock_model):
        """synthesize_pcm_chunks should load model on first request and cache it."""
        models_dir = make_models_dir(tmp_path, sample_rates=[48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        load_counter = [0]
        mock_importer = unittest.mock.MagicMock()

        def counting_load_pickle(*args, **kwargs):
            load_counter[0] += 1
            return mock_model

        mock_importer.load_pickle = counting_load_pickle

        with unittest.mock.patch(
            "src.tts.engine.torch.package.PackageImporter",
            return_value=mock_importer,
        ):
            storage = YamlDataStorage(config_model)
            engine = SileroTTSEngine(
                config=config,
                storage=storage,
                text_sentenizer_factory=TextSentenizerFactory(),
                text_normalizer_factory=None,
            )
            await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")
            await collect_sentences(engine, "world", "ru_RU-v5_5_ru-aidar")

        assert load_counter[0] == 1

    @pytest.mark.asyncio
    async def test_synthesize_per_model_semaphore_limits_concurrent(
        self, tmp_path, mock_package_importer
    ):
        """synthesize_pcm_chunks should use per-model semaphores to limit concurrent requests."""
        models_dir = make_models_dir(tmp_path, sample_rates=[48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )
        await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

    @pytest.mark.asyncio
    async def test_synthesize_cuda_unavailable_falls_back_to_cpu(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """Should fall back to CPU when CUDA is requested but unavailable."""
        models_dir = make_models_dir(tmp_path, sample_rates=[48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cuda",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        class FakeModule:
            @staticmethod
            def is_available():
                return False

            @staticmethod
            def to(device):
                assert device.type == "cpu"

        mock_model.to = FakeModule.to

        with unittest.mock.patch.object(torch, "cuda", FakeModule(), create=True):
            storage = YamlDataStorage(config_model)
            engine = SileroTTSEngine(
                config=config,
                storage=storage,
                text_sentenizer_factory=TextSentenizerFactory(),
                text_normalizer_factory=None,
            )
            results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert len(results) > 0
        r = results[0]
        assert isinstance(r.audio, bytes)
        assert r.sample_rate == 48000
        assert r.bytes_per_sample == BYTES_PER_SAMPLE
        assert r.channels == CHANNELS

    @pytest.mark.asyncio
    async def test_synthesize_xpu_unavailable_falls_back_to_cpu(
        self, tmp_path, mock_package_importer, mock_model
    ):
        """Should fall back to CPU when XPU is requested but unavailable."""
        models_dir = make_models_dir(tmp_path, sample_rates=[48000])
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="xpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=models_dir,
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        class FakeModule:
            @staticmethod
            def is_available():
                return False

            @staticmethod
            def to(device):
                assert device.type == "cpu"

        mock_model.to = FakeModule.to

        with unittest.mock.patch.object(torch, "xpu", FakeModule(), create=True):
            storage = YamlDataStorage(config_model)
            engine = SileroTTSEngine(
                config=config,
                storage=storage,
                text_sentenizer_factory=TextSentenizerFactory(),
                text_normalizer_factory=None,
            )
            results = await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert len(results) > 0
        r = results[0]
        assert isinstance(r.audio, bytes)
        assert r.sample_rate == 48000
        assert r.bytes_per_sample == BYTES_PER_SAMPLE
        assert r.channels == CHANNELS

    @pytest.mark.asyncio
    async def test_synthesize_raises_on_malformed_models_yml(self, tmp_path, default_tts_config):
        """synthesize_pcm_chunks should raise TTSEngineError on malformed models.yml."""
        models_dir = make_models_dir(tmp_path, yml_content=b"tts_models:\n  invalid: [")
        yml_hash = hash_models_yml(models_yml_path(models_dir))

        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=str(models_dir),
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        with pytest.raises(TTSEngineError) as exc_info:
            await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert "Failed to parse the models configuration file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_synthesize_raises_on_model_not_in_registry(self, tmp_path, default_tts_config):
        """synthesize_pcm_chunks should raise TTSEngineError when model missing from registry."""
        models_dir = make_models_dir(
            tmp_path,
            yml_content=b"tts_models:\n  ru:\n    other_model:\n      latest:\n        package: 'http://x'\n",
        )
        yml_hash = hash_models_yml(models_yml_path(models_dir))
        config = TtsConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=str(models_dir),
            models_yml_url="https://example.com",
            models_yml_hash=yml_hash,
        )
        config_model = PredefinedData(
            models=[make_model()],
            voices=[make_voice(voice_id="ru_RU-v5_5_ru-aidar", name="aidar")],
        )

        storage = YamlDataStorage(config_model)
        engine = SileroTTSEngine(
            config=config,
            storage=storage,
            text_sentenizer_factory=TextSentenizerFactory(),
            text_normalizer_factory=None,
        )

        with pytest.raises(TTSEngineError) as exc_info:
            await collect_sentences(engine, "hello", "ru_RU-v5_5_ru-aidar")

        assert "Failed to load model" in str(exc_info.value)
