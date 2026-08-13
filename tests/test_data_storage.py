import io

import pytest
from loguru import logger

from src.tts.data_storage import YamlDataStorage
from src.tts.models import EngineType, NormalizationType, PredefinedData, TextFormat, Voice
from tests.helpers import make_model


class TestYamlDataStorageInit:
    """Tests for SileroTTSYamlConfigStorage initialization."""

    def test_init_accepts_config_model(self):
        """Should accept TTSConfigModel and expose get_voice."""

        config_model = PredefinedData(
            models=[make_model()],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                )
            ],
        )

        storage = YamlDataStorage(config_model)

        assert storage.get_voice("v5_5_ru-aidar").name == "aidar"


class TestGetVoices:
    """Tests for get_voices() method."""

    def test_get_voices_returns_list(self):
        """get_voices should return a list of Voice objects."""

        config_model = PredefinedData(models=[], voices=[])
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert isinstance(result, list)

    def test_get_voices_returns_voice_objects(self):
        """get_voices should return list of Voice objects with id field."""

        config_model = PredefinedData(
            models=[make_model()],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 1
        assert result[0].id == "v5_5_ru-aidar"
        assert result[0].model_id == "v5_5_ru"

    def test_get_voices_includes_all_voices(self):
        """get_voices should include all voices."""

        config_model = PredefinedData(
            models=[make_model()],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                ),
                Voice(
                    id="v5_5_ru-baya",
                    name="baya",
                    speaker="baya",
                    model_id="v5_5_ru",
                ),
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 2
        assert result[0].name == "aidar"
        assert result[1].name == "baya"

    def test_get_voices_from_all_models(self):
        """get_voices should include voices from all models."""

        config_model = PredefinedData(
            models=[make_model(), make_model(id="v3_en")],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                ),
                Voice(
                    id="v3_en-en_0",
                    name="en_0",
                    speaker="en_0",
                    model_id="v3_en",
                ),
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 2


class TestGetVoice:
    """Tests for get_voice() method."""

    def test_get_voice_returns_correct_config(self):
        """get_voice should return Voice for the given voice_id."""

        config_model = PredefinedData(
            models=[make_model()],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        voice = storage.get_voice("v5_5_ru-aidar")
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_5_ru"


class TestYamlConstructor:
    """Tests for constructing from a YAML file path."""

    def test_loads_config_from_yaml_path(self, tmp_path):
        """Should load config from a YAML file path with merged structure."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voice = storage.get_voice("v5_5_ru-aidar")
        assert voice.name == "aidar"
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_5_ru"

    def test_loaded_voices_have_voice_configs(self, tmp_path):
        """get_voices should return Voice objects with computed id."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voices = storage.get_voices()
        assert len(voices) == 1
        assert voices[0].id == "v5_5_ru-aidar"
        assert voices[0].model_id == "v5_5_ru"

    def test_missing_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML without speaker field should default speaker to voice_name."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("v5_5_ru-aidar")
        assert voice.speaker == "aidar"

    def test_empty_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML with speaker: '' should default speaker to voice_name."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: ""
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("v5_5_ru-aidar")
        assert voice.speaker == "aidar"


class TestLocaleLessSchema:
    """Tests for the new flat schema: voices live under models, IDs have no locale prefix."""

    def test_loads_locale_less_voices_from_flat_schema(self, tmp_path):
        """Loading a flat-schema YAML yields locale-less Voice objects with model-voice IDs."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    warmup: true
    voices:
      - name: aidar
      - name: eugene
  v3_en:
    engine_type: silero
    languages: [en]
    voices:
      - name: henry
        speaker: en_2
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert [v.id for v in storage.get_voices()] == [
            "v5_5_ru-aidar",
            "v5_5_ru-eugene",
            "v3_en-henry",
        ]
        assert not hasattr(storage.get_voice("v5_5_ru-aidar"), "locale")
        assert storage.get_voice("v3_en-henry").speaker == "en_2"
        assert storage.get_voice("v3_en-henry").name == "henry"
        assert storage.get_model("v5_5_ru").warmup is True

    def test_voices_sharing_speaker_load_with_distinct_name_ids(self, tmp_path):
        """Two voices sharing a speaker under one model load with distinct name-based IDs."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar-soft
        speaker: aidar
      - name: aidar-loud
        speaker: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert [v.id for v in storage.get_voices()] == [
            "v5_5_ru-aidar-soft",
            "v5_5_ru-aidar-loud",
        ]
        assert storage.get_voice("v5_5_ru-aidar-soft").speaker == "aidar"
        assert storage.get_voice("v5_5_ru-aidar-loud").speaker == "aidar"

    def test_duplicate_voice_name_in_one_model_raises_error(self, tmp_path):
        """Two voices with the same name in one model derive the same ID and fail loudly."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
      - name: aidar
        speaker: baya
"""
        )

        with pytest.raises(ValueError, match="v5_5_ru-aidar"):
            YamlDataStorage(str(config_yml))

    def test_same_voice_name_in_different_models_loads(self, tmp_path):
        """Same voice name under different models derives distinct IDs and loads fine."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
  v3_en:
    engine_type: silero
    languages: [en]
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert [v.id for v in storage.get_voices()] == ["v5_5_ru-aidar", "v3_en-aidar"]

    def test_voice_yaml_entries_populate_reference_fields(self, tmp_path):
        """ref_audio, ref_text, and instruct keys in a voice entry parse onto the Voice."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        ref_audio: /audio/aidar.wav
        ref_text: "Hello world"
        instruct: "Speak slowly"
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("v5_5_ru-aidar")

        assert voice.ref_audio == "/audio/aidar.wav"
        assert voice.ref_text == "Hello world"
        assert voice.instruct == "Speak slowly"


class TestEmptyData:
    """Tests for empty/minimal configs."""

    def test_empty_config(self):
        """Should handle empty config with no locales or models."""

        config_model = PredefinedData(models=[], voices=[])
        storage = YamlDataStorage(config_model)

        assert storage.get_voices() == []

    def test_empty_config_from_yaml(self, tmp_path):
        """Should load and handle empty YAML config."""

        config_yml = tmp_path / "empty.yml"
        config_yml.write_text("")

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_voices() == []


class TestYamlEnabledField:
    """Tests for parsing enabled field from YAML config."""

    def test_yaml_enabled_false_disables_model(self, tmp_path):
        """YAML with enabled: false should disable the model."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    enabled: false
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_voices() == []

    def test_yaml_without_enabled_defaults_to_enabled(self, tmp_path):
        """YAML without enabled field should keep the model enabled."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert len(storage.get_voices()) == 1

    def test_yaml_enabled_true_explicitly_enables_model(self, tmp_path):
        """YAML with enabled: true should keep the model enabled."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    enabled: true
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert len(storage.get_voices()) == 1

    def test_yaml_mixed_enabled_and_disabled(self, tmp_path):
        """YAML with mixed enabled/disabled models filters correctly."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    enabled: false
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
  v3_en:
    engine_type: silero
    languages: [en]
    enabled: true
    voices:
      - name: en_0
        speaker: en_0
        model: v3_en
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voices = storage.get_voices()
        assert not any(v.model_id == "v5_5_ru" for v in voices)
        assert any(v.model_id == "v3_en" for v in voices)
        assert any(v.name == "en_0" for v in voices)


class TestGetModel:
    """Tests for get_model() method."""

    def test_get_model_returns_correct_model(self):
        """get_model should return Model for the given model name."""

        config_model = PredefinedData(
            models=[make_model()],
            voices=[],
        )
        storage = YamlDataStorage(config_model)

        m = storage.get_model("v5_5_ru")
        assert m.id == "v5_5_ru"


class TestGetModels:
    def test_get_models_returns_all_enabled_models(self):
        """get_models() returns list of all enabled Model objects."""

        config_model = PredefinedData(
            models=[
                make_model(warmup=True),
                make_model(id="v3_en"),
            ],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                )
            ],
        )

        storage = YamlDataStorage(config_model)
        result = storage.get_models()

        model1 = [model for model in result if model.id == "v5_5_ru"]
        model2 = [model for model in result if model.id == "v3_en"]

        assert isinstance(result, list)
        assert len(result) == 2
        assert model1 is not None
        assert model2 is not None


class TestYamlWarmupField:
    """Tests for parsing warmup field from YAML config."""

    def test_yaml_warmup_true_sets_warmup_on_model(self, tmp_path):
        """YAML with warmup: true should set warmup=True on Model."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    warmup: true
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").warmup is True

    def test_yaml_without_warmup_defaults_to_false(self, tmp_path):
        """YAML without warmup field should default to False."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").warmup is False


class TestYamlHashPrefixField:
    """Tests for parsing hash_prefix field from YAML config."""

    def test_yaml_hash_prefix_sets_hash_prefix_on_model(self, tmp_path):
        """YAML with hash_prefix should set hash_prefix on Model."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    hash_prefix: "a1b2c3d4"
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").hash_prefix == "a1b2c3d4"

    def test_yaml_without_hash_prefix_defaults_to_none(self, tmp_path):
        """YAML without hash_prefix should default to None."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").hash_prefix is None

    def test_yaml_empty_hash_prefix_defaults_to_none(self, tmp_path):
        """YAML with empty hash_prefix should default to None."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    hash_prefix: ""
    voices:
      - name: aidar
        speaker: aidar
        model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").hash_prefix is None


class TestDisabledModel:
    """Tests for model disabling via enabled=False on Model."""

    def test_disabled_model_voices_excluded_from_get_voices(self):
        """get_voices should exclude voices that reference a disabled model."""

        config_model = PredefinedData(
            models=[
                make_model(enabled=False),
                make_model(id="v3_en", enabled=True),
            ],
            voices=[
                Voice(
                    id="v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_5_ru",
                ),
                Voice(
                    id="v3_en-en_0",
                    name="en_0",
                    speaker="en_0",
                    model_id="v3_en",
                ),
            ],
        )

        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert not any(v.model_id == "v5_5_ru" for v in result)
        assert any(v.model_id == "v3_en" for v in result)
        assert any(v.name == "en_0" for v in result)

    def test_disabled_model_get_model_returns_none(self):
        """get_model should return None for a disabled model."""

        config_model = PredefinedData(
            models=[
                make_model(enabled=False),
            ],
            voices=[],
        )

        storage = YamlDataStorage(config_model)

        assert storage.get_model("v5_5_ru") is None


class TestGetPrompt:
    """Tests for get_prompt() method."""

    def test_get_prompt_returns_prompt(self, tmp_path):
        """get_prompt should return Prompt for the given prompt_id."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
prompts:
  - id: p1
    text: "Say hello nicely"
    model: gpt-4
models: {}
voices: []
"""
        )
        storage = YamlDataStorage(str(config_yml))
        prompt = storage.get_prompt("p1")
        assert prompt is not None
        assert prompt.id == "p1"
        assert prompt.text == "Say hello nicely"
        assert prompt.model == "gpt-4"

    def test_get_prompt_returns_none_for_missing_id(self, tmp_path):
        """get_prompt should return None for unknown prompt_id."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
prompts:
  - id: p1
    text: "Say hello nicely"
    model: gpt-4
models: {}
voices: []
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_prompt("unknown") is None

    def test_get_prompt_from_empty_prompts(self, tmp_path):
        """get_prompt should return None when prompts list is empty."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
prompts: []
models: {}
voices: []
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_prompt("p1") is None

    def test_get_prompt_from_missing_prompts_key(self, tmp_path):
        """get_prompt should return None when prompts key is absent."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models: {}
voices: []
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_prompt("p1") is None


class TestGetVoiceNormalization:
    """Tests for get_voice_normalization() method."""

    def test_get_voice_normalization_returns_normalization(self, tmp_path):
        """get_voice_normalization returns VoiceNormalization for voice + text_format + language."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: p1
"""
        )
        storage = YamlDataStorage(str(config_yml))
        vn = storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "ru")
        assert vn is not None
        assert vn.voice_id == "v5_5_ru-aidar"
        assert vn.text_format == TextFormat.TEXT
        assert vn.language == "ru"
        assert vn.type == NormalizationType.OPENAI
        assert vn.enabled is True
        assert vn.prompt_id == "p1"

    def test_get_voice_normalization_mismatched_language_returns_none(self, tmp_path):
        """get_voice_normalization returns None for a language with no override."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: p1
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "en") is None

    def test_get_voice_normalization_multiple_languages(self, tmp_path):
        """get_voice_normalization distinguishes overrides for different languages."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: p1
          en:
            text:
              enabled: false
              type: simple
"""
        )
        storage = YamlDataStorage(str(config_yml))
        ru_vn = storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "ru")
        en_vn = storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "en")
        assert ru_vn.language == "ru"
        assert ru_vn.enabled is True
        assert en_vn.language == "en"
        assert en_vn.enabled is False

    def test_get_voice_normalization_lenient_defaults(self, tmp_path):
        """enabled defaults to true, type defaults to simple, invalid format keys skipped."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              prompt_id: p1
            bogus_format:
              enabled: false
"""
        )
        storage = YamlDataStorage(str(config_yml))
        vn = storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "ru")
        assert vn is not None
        assert vn.enabled is True
        assert vn.type == NormalizationType.SIMPLE
        assert vn.prompt_id == "p1"

    def test_get_voice_normalization_returns_none_for_unknown_voice(self, tmp_path):
        """get_voice_normalization returns None for unknown voice_id."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("unknown-voice", TextFormat.TEXT, "ru") is None

    def test_get_voice_normalization_returns_none_for_unknown_format(self, tmp_path):
        """get_voice_normalization returns None for text_format not in normalization."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.SSML, "ru") is None

    def test_get_voice_normalization_voice_without_normalization(self, tmp_path):
        """get_voice_normalization returns None when voice has no normalization section."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "ru") is None

    def test_get_voice_normalization_disabled_entry(self, tmp_path):
        """get_voice_normalization returns entry even if enabled=False."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: false
              type: simple
"""
        )
        storage = YamlDataStorage(str(config_yml))
        vn = storage.get_voice_normalization("v5_5_ru-aidar", TextFormat.TEXT, "ru")
        assert vn is not None
        assert vn.enabled is False
        assert vn.type == NormalizationType.SIMPLE


class TestModelCapabilities:
    """Tests for parsing and validating Model capability fields from YAML."""

    def test_missing_languages_raises_value_error(self, tmp_path):
        """A model without a languages list fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError, match="languages"):
            YamlDataStorage(str(config_yml))

    @pytest.mark.parametrize(
        ("yaml_value", "expected"),
        [
            ("silero", EngineType.SILERO),
            ("qwen", EngineType.QWEN),
            ("openai", EngineType.OPENAI),
        ],
    )
    def test_engine_type_maps_to_enum(self, tmp_path, yaml_value, expected):
        """engine_type maps the YAML name to the EngineType member."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            f"""
models:
  v5_5_ru:
    engine_type: {yaml_value}
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").engine_type is expected

    def test_missing_engine_type_raises_value_error(self, tmp_path):
        """A model without engine_type fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError, match="engine_type"):
            YamlDataStorage(str(config_yml))

    def test_unknown_engine_type_raises_value_error(self, tmp_path):
        """An unrecognized engine_type value fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: klingon
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError, match="engine_type"):
            YamlDataStorage(str(config_yml))

    def test_languages_parse_as_trimmed_list(self, tmp_path):
        """languages parses into a list with each entry whitespace-trimmed."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages:
      - " ru "
      - "  en"
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model("v5_5_ru").languages == ["ru", "en"]

    def test_empty_languages_raises_value_error(self, tmp_path):
        """An explicitly empty languages list fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: []
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError, match="languages"):
            YamlDataStorage(str(config_yml))

    def test_ssml_supported_and_language_auto_detected_default_to_false(self, tmp_path):
        """Omitted ssml_supported and language_auto_detected default to false."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))
        model = storage.get_model("v5_5_ru")

        assert model.ssml_supported is False
        assert model.language_auto_detected is False

    def test_ssml_supported_and_language_auto_detected_parse_true(self, tmp_path):
        """Declared true ssml_supported and language_auto_detected parse as true."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    ssml_supported: true
    language_auto_detected: true
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))
        model = storage.get_model("v5_5_ru")

        assert model.ssml_supported is True
        assert model.language_auto_detected is True


class TestActiveModelsAllowlist:
    """Tests for the active_models runtime allowlist."""

    def test_active_model_is_served(self):
        """A model listed in active_models and enabled is served; unlisted models' voices are dropped."""
        config_model = PredefinedData(
            models=[
                make_model(),
                make_model(id="v3_en"),
            ],
            voices=[
                Voice(id="v5_5_ru-aidar", name="aidar", speaker="aidar", model_id="v5_5_ru"),
                Voice(id="v3_en-en_0", name="en_0", speaker="en_0", model_id="v3_en"),
            ],
        )

        storage = YamlDataStorage(config_model, active_models=["v5_5_ru"])

        assert storage.get_model("v5_5_ru") is not None
        assert storage.get_model("v3_en") is None
        assert not any(v.model_id == "v3_en" for v in storage.get_voices())

    def test_listed_but_disabled_model_is_not_served_and_warns(self):
        """A model listed in active_models but disabled is not served and logs a warning."""
        config_model = PredefinedData(
            models=[
                make_model(),
                make_model(id="v3_en", enabled=False),
            ],
            voices=[
                Voice(id="v5_5_ru-aidar", name="aidar", speaker="aidar", model_id="v5_5_ru"),
                Voice(id="v3_en-en_0", name="en_0", speaker="en_0", model_id="v3_en"),
            ],
        )

        sink = io.StringIO()
        handler = logger.add(sink, level="WARNING")
        try:
            storage = YamlDataStorage(config_model, active_models=["v5_5_ru", "v3_en"])
        finally:
            logger.remove(handler)

        assert storage.get_model("v3_en") is None
        assert not any(v.model_id == "v3_en" for v in storage.get_voices())
        assert "v3_en" in sink.getvalue()
