from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from src.tts.models import (
    EngineType,
    Model,
    NormalizationType,
    PredefinedData,
    Prompt,
    TextFormat,
    TtsResult,
    Voice,
    VoiceNormalization,
)


class TestEngineType:
    def test_engine_type_has_silero_qwen_openai_values(self):
        """EngineType exposes SILERO, QWEN, and OPENAI members with expected values."""
        assert EngineType.SILERO.value == "silero"
        assert EngineType.QWEN.value == "qwen"
        assert EngineType.OPENAI.value == "openai"


class TestModel:
    def test_model_requires_engine_type(self):
        """Model.engine_type is required — constructing without it raises TypeError."""
        with pytest.raises(TypeError):
            Model(id="test_model")

    def test_model_stores_engine_type(self):
        """Model stores the given engine_type."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.engine_type is EngineType.SILERO

    def test_model_accepts_any_engine_type(self):
        """Model accepts each EngineType member."""
        for engine_type in EngineType:
            model = Model(id="test_model", engine_type=engine_type)
            assert model.engine_type is engine_type

    def test_model_ssml_supported_defaults_to_false(self):
        """Model.ssml_supported defaults to False."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.ssml_supported is False

    def test_model_ssml_supported_can_be_set_to_true(self):
        """Model(ssml_supported=True) sets ssml_supported to True."""
        model = Model(id="test_model", engine_type=EngineType.SILERO, ssml_supported=True)
        assert model.ssml_supported is True

    def test_model_language_auto_detected_defaults_to_false(self):
        """Model.language_auto_detected defaults to False."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.language_auto_detected is False

    def test_model_language_auto_detected_can_be_set_to_true(self):
        """Model(language_auto_detected=True) sets language_auto_detected to True."""
        model = Model(id="test_model", engine_type=EngineType.SILERO, language_auto_detected=True)
        assert model.language_auto_detected is True

    def test_model_languages_defaults_to_empty_list(self):
        """Model.languages defaults to an empty list."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.languages == []

    def test_model_languages_stores_declared_languages(self):
        """Model stores the declared list of languages."""
        model = Model(id="test_model", engine_type=EngineType.SILERO, languages=["ru", "en"])
        assert model.languages == ["ru", "en"]

    def test_model_warmup_defaults_to_false(self):
        """Model.warmup defaults to False."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.warmup is False

    def test_model_warmup_can_be_set_to_true(self):
        """Model(warmup=True) sets warmup to True."""
        model = Model(id="test_model", engine_type=EngineType.SILERO, warmup=True)
        assert model.warmup is True

    def test_model_hash_prefix_defaults_to_none(self):
        """Model.hash_prefix defaults to None."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        assert model.hash_prefix is None

    def test_model_hash_prefix_can_be_set(self):
        """Model(hash_prefix=...) stores the value."""
        model = Model(id="test_model", engine_type=EngineType.SILERO, hash_prefix="a1b2c3")
        assert model.hash_prefix == "a1b2c3"

    def test_model_is_frozen(self):
        """Model dataclass is immutable (frozen)."""
        model = Model(id="test_model", engine_type=EngineType.SILERO)
        with pytest.raises(FrozenInstanceError):
            model.engine_type = EngineType.QWEN


class TestVoice:
    def test_voice_has_all_fields(self):
        """Voice dataclass has id, name, speaker, model_id fields."""
        voice = Voice(
            id="v5_5_ru-aidar",
            name="aidar",
            speaker="aidar",
            model_id="v5_5_ru",
        )
        assert voice.id == "v5_5_ru-aidar"
        assert voice.name == "aidar"
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_5_ru"

    def test_voice_has_optional_reference_fields(self):
        """Voice can be constructed with reference audio/text and instruct fields."""
        voice = Voice(
            id="v5_5_ru-aidar",
            name="aidar",
            speaker="aidar",
            model_id="v5_5_ru",
            ref_audio="path/to/ref.wav",
            ref_text="reference text",
            instruct="instructive prompt",
        )
        assert voice.ref_audio == "path/to/ref.wav"
        assert voice.ref_text == "reference text"
        assert voice.instruct == "instructive prompt"

    def test_voice_can_be_created_with_only_required_fields(self):
        """Voice can be constructed with only the 4 essential fields."""
        voice = Voice(
            id="v5_5_ru-aidar",
            name="aidar",
            speaker="aidar",
            model_id="v5_5_ru",
        )
        assert voice.id == "v5_5_ru-aidar"
        assert voice.name == "aidar"
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_5_ru"

    def test_voice_is_frozen(self):
        """Voice dataclass is immutable (frozen)."""
        voice = Voice(
            id="v5_5_ru-aidar",
            name="aidar",
            speaker="aidar",
            model_id="v5_5_ru",
        )
        with pytest.raises(FrozenInstanceError):
            voice.speaker = "baya"


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


class TestPredefinedData:
    def test_predefined_data_has_models_and_voices(self):
        """PredefinedData dataclass has models list and voices list."""
        models = [Model(id="v3_en", engine_type=EngineType.SILERO)]
        voices = [
            Voice(
                id="en_US-v3_en-en_0",
                name="en_0",
                speaker="en_0",
                model_id="v3_en",
            )
        ]
        data = PredefinedData(models=models, voices=voices)
        assert data.models == models
        assert data.voices == voices

    def test_predefined_data_is_frozen(self):
        """PredefinedData dataclass is immutable (frozen)."""
        data = PredefinedData(models=[], voices=[])
        with pytest.raises(FrozenInstanceError):
            data.models = []


class TestTTSResult:
    def test_tts_result_has_all_fields(self):
        """TTSResult dataclass has audio (np.ndarray), sample_rate, bytes_per_sample, channels."""
        audio = np.array([0, 1, 2, 3], dtype=np.int16)
        result = TtsResult(audio=audio, sample_rate=48000, bytes_per_sample=2, channels=1)
        assert isinstance(result.audio, np.ndarray)
        assert np.array_equal(result.audio, audio)
        assert result.sample_rate == 48000
        assert result.bytes_per_sample == 2
        assert result.channels == 1


class TestContiguousAudio:
    """A Chunk's audio can be addressed as raw bytes, without a copy on the way."""

    def test_strided_audio_becomes_contiguous(self):
        """Audio with gaps between its samples reaches the caller as one run of samples."""
        strided = np.zeros(8, dtype=np.int16)[::2]
        assert not strided.flags["C_CONTIGUOUS"]

        result = TtsResult(audio=strided, sample_rate=48000, bytes_per_sample=2, channels=1)

        assert result.audio.flags["C_CONTIGUOUS"]
        assert np.array_equal(result.audio, strided)

    def test_contiguous_audio_is_not_copied(self):
        """Audio already contiguous is handed straight over, so no copy is paid for."""
        audio = np.zeros(8, dtype=np.int16)

        result = TtsResult(audio=audio, sample_rate=48000, bytes_per_sample=2, channels=1)

        assert result.audio is audio
