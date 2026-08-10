from dataclasses import FrozenInstanceError

import pytest

from src.config import Settings
from src.tts.exceptions import TTSEngineError
from src.tts.models import (
    Model,
    NormalizationType,
    PredefinedData,
    Prompt,
    TextFormat,
    TTSConfig,
    TTSResult,
    Voice,
    VoiceNormalization,
)


class TestModel:
    def test_model_has_name_and_language_fields(self):
        """Model dataclass has name and language fields."""
        model = Model(id="test_model", language="en")
        assert model.id == "test_model"
        assert model.language == "en"

    def test_model_warmup_defaults_to_false(self):
        """Model.warmup defaults to False."""
        model = Model(id="test_model", language="en")
        assert model.warmup is False

    def test_model_warmup_can_be_set_to_true(self):
        """Model(language, warmup=True) sets warmup to True."""
        model = Model(id="test_model", language="en", warmup=True)
        assert model.warmup is True

    def test_model_hash_prefix_defaults_to_none(self):
        """Model.hash_prefix defaults to None."""
        model = Model(id="test_model", language="en")
        assert model.hash_prefix is None

    def test_model_hash_prefix_can_be_set(self):
        """Model(name, language, hash_prefix=...) stores the value."""
        model = Model(id="test_model", language="en", hash_prefix="a1b2c3")
        assert model.hash_prefix == "a1b2c3"

    def test_model_is_frozen(self):
        """Model dataclass is immutable (frozen)."""
        model = Model(id="test_model", language="en")
        with pytest.raises(FrozenInstanceError):
            model.language = "fr"


class TestVoice:
    def test_voice_has_all_fields(self):
        """Voice dataclass has id, name, speaker, model, locale fields."""
        voice = Voice(
            id="en_US-v3_en-en_0",
            name="en_0",
            speaker="en_0",
            model_id="v3_en",
            locale="en_US",
        )
        assert voice.id == "en_US-v3_en-en_0"
        assert voice.name == "en_0"
        assert voice.speaker == "en_0"
        assert voice.model_id == "v3_en"
        assert voice.locale == "en_US"

    def test_voice_can_be_created_without_gender(self):
        """Voice can be constructed with only the 5 essential fields — no gender required."""
        voice = Voice(
            id="en_US-v3_en-en_0",
            name="en_0",
            speaker="en_0",
            model_id="v3_en",
            locale="en_US",
        )
        assert voice.id == "en_US-v3_en-en_0"
        assert voice.name == "en_0"
        assert voice.speaker == "en_0"
        assert voice.model_id == "v3_en"
        assert voice.locale == "en_US"

    def test_voice_is_frozen(self):
        """Voice dataclass is immutable (frozen)."""
        voice = Voice(
            id="en_US-v3_en-en_0",
            name="en_0",
            speaker="en_0",
            model_id="v3_en",
            locale="en_US",
        )
        with pytest.raises(FrozenInstanceError):
            voice.speaker = "en_1"


class TestPrompt:
    def test_prompt_has_id_text_and_model_fields(self):
        """Prompt dataclass has id, text, and model fields."""
        prompt = Prompt(id="p1", text="Say hello nicely", model="gpt-4")
        assert prompt.id == "p1"
        assert prompt.text == "Say hello nicely"
        assert prompt.model == "gpt-4"

    def test_prompt_is_frozen(self):
        """Prompt dataclass is immutable (frozen)."""
        prompt = Prompt(id="p1", text="Say hello nicely", model="gpt-4")
        with pytest.raises(FrozenInstanceError):
            prompt.text = "Changed"


class TestVoiceNormalization:
    def test_voice_normalization_has_all_fields(self):
        """VoiceNormalization dataclass has voice_id, text_format, language, type, enabled, prompt_id."""
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="p1",
        )
        assert vn.voice_id == "v1"
        assert vn.text_format == TextFormat.TEXT
        assert vn.language == "ru"
        assert vn.type == NormalizationType.OPENAI
        assert vn.enabled is True
        assert vn.prompt_id == "p1"

    def test_voice_normalization_prompt_id_defaults_to_none(self):
        """VoiceNormalization.prompt_id defaults to None."""
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=False,
        )
        assert vn.prompt_id is None

    def test_voice_normalization_is_frozen(self):
        """VoiceNormalization dataclass is immutable (frozen)."""
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=True,
        )
        with pytest.raises(FrozenInstanceError):
            vn.enabled = False


class TestTTSConfigModel:
    def test_tts_config_model_has_models_and_voices(self):
        """TTSConfigModel dataclass has models list and voices list."""
        models = [Model(id="v3_en", language="en")]
        voices = [
            Voice(
                id="en_US-v3_en-en_0",
                name="en_0",
                speaker="en_0",
                model_id="v3_en",
            )
        ]
        config = PredefinedData(models=models, voices=voices)
        assert config.models == models
        assert config.voices == voices

    def test_tts_config_model_is_frozen(self):
        """TTSConfigModel dataclass is immutable (frozen)."""
        config = PredefinedData(models=[], voices=[])
        with pytest.raises(FrozenInstanceError):
            config.models = []


class TestTTSConfig:
    def test_tts_config_has_max_models_field(self):
        """TTSConfig dataclass has max_models field."""
        config = TTSConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=5,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=".models/silero",
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=None,
        )
        assert config.max_models == 5

    def test_tts_config_accepts_models_yml_url_and_hash(self):
        """TTSConfig accepts models_yml_url and models_yml_hash."""
        settings = Settings()
        config = TTSConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=".models/silero",
            models_yml_url=str(settings.silero.models_yml_url),
            models_yml_hash=settings.silero.models_yml_hash,
        )
        assert str(config.models_yml_url) == str(settings.silero.models_yml_url)
        assert config.models_yml_hash == settings.silero.models_yml_hash

    def test_tts_config_models_yml_hash_accepts_none(self):
        """TTSConfig.models_yml_hash accepts None (skip validation)."""
        config = TTSConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=".models/silero",
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=None,
        )
        assert config.models_yml_hash is None

    def test_tts_config_is_frozen(self):
        """TTSConfig dataclass is immutable (frozen)."""
        config = TTSConfig(
            device="cpu",
            inference_timeout=5,
            frame_duration=50,
            sample_rate=48000,
            max_models=2,
            cache_half_life=60,
            max_concurrent_sentences_per_model=2,
            max_sentence_chars=48000,
            models_dir=".models/silero",
            models_yml_url="https://example.com/models.yml",
            models_yml_hash=None,
        )
        with pytest.raises(FrozenInstanceError):
            config.max_models = 3


class TestExceptions:
    def test_tts_engine_error_message_only(self):
        """TTSEngineError accepts only message — no locale/voice/status_code."""
        err = TTSEngineError("test error")
        assert str(err) == "test error"
        assert not hasattr(err, "locale")
        assert not hasattr(err, "voice")
        assert not hasattr(err, "status_code")


class TestTTSResult:
    def test_tts_result_has_all_fields(self):
        """TTSResult dataclass has audio, sample_rate, bytes_per_sample, channels."""
        audio = b"\x00\x00\x00\x00"
        result = TTSResult(audio=audio, sample_rate=48000, bytes_per_sample=2, channels=1)
        assert result.audio == audio
        assert result.sample_rate == 48000
        assert result.bytes_per_sample == 2
        assert result.channels == 1
