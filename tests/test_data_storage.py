import io
from pathlib import Path

import pytest
from loguru import logger

from src.tts.data_storage import YamlDataStorage
from src.tts.models import (
    EngineType,
    ModelInfo,
    NormalizationType,
    PredefinedData,
    TextFormat,
    Voice,
)
from tests.helpers import make_model_info


def write_data_file(tmp_path: Path, contents: str, name: str = "data.yml") -> Path:
    """Write a data file and hand back its path, ready to be read as written."""
    path = tmp_path / name
    path.write_text(contents)

    return path


MODEL_WITH_VOICE = """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
"""


class TestYamlDataStorageInit:
    """Tests for SileroTTSYamlConfigStorage initialization."""

    def test_init_accepts_config_model(self):
        """Should accept TTSConfigModel and expose get_voice."""

        config_model = PredefinedData(
            models=[make_model_info()],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
                )
            ],
        )

        storage = YamlDataStorage(config_model)

        assert storage.get_voice("v5_6_ru-aidar").name == "aidar"


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
            models=[make_model_info()],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 1
        assert result[0].id == "v5_6_ru-aidar"
        assert result[0].model_id == "v5_6_ru"

    def test_get_voices_includes_all_voices(self):
        """get_voices should include all voices."""

        config_model = PredefinedData(
            models=[make_model_info()],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
                ),
                Voice(
                    id="v5_6_ru-baya",
                    name="baya",
                    speaker="baya",
                    model_id="v5_6_ru",
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
            models=[make_model_info(), make_model_info(id="v3_en")],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
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
            models=[make_model_info()],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        voice = storage.get_voice("v5_6_ru-aidar")
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_6_ru"


class TestYamlConstructor:
    """Tests for constructing from a YAML file path."""

    def test_loads_config_from_yaml_path(self, tmp_path):
        """Should load config from a YAML file path with merged structure."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voice = storage.get_voice("v5_6_ru-aidar")
        assert voice.name == "aidar"
        assert voice.speaker == "aidar"
        assert voice.model_id == "v5_6_ru"

    def test_loaded_voices_have_voice_configs(self, tmp_path):
        """get_voices should return Voice objects with computed id."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voices = storage.get_voices()
        assert len(voices) == 1
        assert voices[0].id == "v5_6_ru-aidar"
        assert voices[0].model_id == "v5_6_ru"

    def test_missing_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML without speaker field should default speaker to voice_name."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("v5_6_ru-aidar")
        assert voice.speaker == "aidar"

    def test_empty_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML with speaker: '' should default speaker to voice_name."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: ""
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("v5_6_ru-aidar")
        assert voice.speaker == "aidar"


class TestLocaleLessSchema:
    """Tests for the new flat schema: voices live under models, IDs have no locale prefix."""

    def test_loads_locale_less_voices_from_flat_schema(self, tmp_path):
        """Loading a flat-schema YAML yields locale-less Voice objects with model-voice IDs."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
            "v5_6_ru-aidar",
            "v5_6_ru-eugene",
            "v3_en-henry",
        ]
        assert not hasattr(storage.get_voice("v5_6_ru-aidar"), "locale")
        assert storage.get_voice("v3_en-henry").speaker == "en_2"
        assert storage.get_voice("v3_en-henry").name == "henry"
        assert storage.get_model_info("v5_6_ru").warmup is True

    def test_voices_sharing_speaker_load_with_distinct_name_ids(self, tmp_path):
        """Two voices sharing a speaker under one Model Info load with distinct name-based IDs."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
            "v5_6_ru-aidar-soft",
            "v5_6_ru-aidar-loud",
        ]
        assert storage.get_voice("v5_6_ru-aidar-soft").speaker == "aidar"
        assert storage.get_voice("v5_6_ru-aidar-loud").speaker == "aidar"

    def test_duplicate_voice_name_in_one_model_info_raises_error(self, tmp_path):
        """Two voices with the same name in one Model Info derive the same ID and fail loudly."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
      - name: aidar
        speaker: baya
"""
        )

        with pytest.raises(ValueError, match="v5_6_ru-aidar"):
            YamlDataStorage(str(config_yml))

    def test_same_voice_name_in_different_models_loads(self, tmp_path):
        """Same voice name under different models derives distinct IDs and loads fine."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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

        assert [v.id for v in storage.get_voices()] == ["v5_6_ru-aidar", "v3_en-aidar"]

    def test_voice_yaml_entries_populate_reference_fields(self, tmp_path):
        """ref_audio, ref_text, and instruct keys in a voice entry parse onto the Voice."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
        voice = storage.get_voice("v5_6_ru-aidar")

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

    def test_yaml_enabled_false_disables_model_info(self, tmp_path):
        """YAML with enabled: false should disable the Model Info."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    enabled: false
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_voices() == []

    def test_yaml_without_enabled_defaults_to_enabled(self, tmp_path):
        """YAML without enabled field should keep the Model Info enabled."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert len(storage.get_voices()) == 1

    def test_yaml_enabled_true_explicitly_enables_model_info(self, tmp_path):
        """YAML with enabled: true should keep the Model Info enabled."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    enabled: true
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert len(storage.get_voices()) == 1

    def test_yaml_mixed_enabled_and_disabled(self, tmp_path):
        """YAML with mixed enabled/disabled Model Infos filters correctly."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    enabled: false
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
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
        assert not any(v.model_id == "v5_6_ru" for v in voices)
        assert any(v.model_id == "v3_en" for v in voices)
        assert any(v.name == "en_0" for v in voices)


class TestGetModelInfo:
    """Tests for get_model_info() method."""

    def test_get_model_info_returns_correct_model_info(self):
        """get_model_info should return the Model Info for the given model id."""

        config_model = PredefinedData(
            models=[make_model_info()],
            voices=[],
        )
        storage = YamlDataStorage(config_model)

        model_info = storage.get_model_info("v5_6_ru")
        assert model_info.id == "v5_6_ru"


class TestGetModelInfos:
    def test_get_model_infos_returns_all_enabled_models(self):
        """get_model_infos() returns the list of all enabled Model Info objects."""

        config_model = PredefinedData(
            models=[
                make_model_info(warmup=True),
                make_model_info(id="v3_en"),
            ],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
                )
            ],
        )

        storage = YamlDataStorage(config_model)
        result = storage.get_model_infos()

        model_info1 = [model_info for model_info in result if model_info.id == "v5_6_ru"]
        model_info2 = [model_info for model_info in result if model_info.id == "v3_en"]

        assert isinstance(result, list)
        assert len(result) == 2
        assert model_info1 is not None
        assert model_info2 is not None


class TestModelInfoFromYaml:
    """The data file is read into Model Info, the configuration a TTS Engine is built for."""

    def test_yaml_entry_becomes_model_info(self, tmp_path):
        """A YAML entry is handed back as a ModelInfo."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert type(storage.get_model_info("v5_6_ru")) is ModelInfo


class TestYamlWarmupField:
    """Tests for parsing warmup field from YAML config."""

    def test_yaml_warmup_true_sets_warmup_on_model_info(self, tmp_path):
        """YAML with warmup: true should set warmup=True on the Model Info."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    warmup: true
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").warmup is True

    def test_yaml_without_warmup_defaults_to_false(self, tmp_path):
        """YAML without warmup field should default to False."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").warmup is False


class TestYamlHashPrefixField:
    """Tests for parsing hash_prefix field from YAML config."""

    def test_yaml_hash_prefix_sets_hash_prefix_on_model_info(self, tmp_path):
        """YAML with hash_prefix should set hash_prefix on the Model Info."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    hash_prefix: "a1b2c3d4"
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").hash_prefix == "a1b2c3d4"

    def test_yaml_without_hash_prefix_defaults_to_none(self, tmp_path):
        """YAML without hash_prefix should default to None."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").hash_prefix is None

    def test_yaml_empty_hash_prefix_defaults_to_none(self, tmp_path):
        """YAML with empty hash_prefix should default to None."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    hash_prefix: ""
    voices:
      - name: aidar
        speaker: aidar
        model: v5_6_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").hash_prefix is None


class TestYamlRevisionField:
    """Tests for parsing revision field from YAML config."""

    def test_yaml_revision_sets_revision_on_model_info(self, tmp_path):
        """YAML with revision should set revision on the Model Info."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  qwen3_tts:
    engine_type: qwen3
    languages: [en]
    revision: "0123456789abcdef"
    voices:
      - name: clone
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("qwen3_tts").revision == "0123456789abcdef"

    def test_yaml_without_revision_defaults_to_none(self, tmp_path):
        """YAML without revision should default to None."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  qwen3_tts:
    engine_type: qwen3
    languages: [en]
    voices:
      - name: clone
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("qwen3_tts").revision is None

    def test_yaml_empty_revision_defaults_to_none(self, tmp_path):
        """YAML with empty revision should default to None."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  qwen3_tts:
    engine_type: qwen3
    languages: [en]
    revision: ""
    voices:
      - name: clone
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("qwen3_tts").revision is None

    def test_yaml_revision_and_hash_prefix_stay_separate(self, tmp_path):
        """A revision pin and a checksum pin are read as the distinct guarantees they are."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  qwen3_tts:
    engine_type: qwen3
    languages: [en]
    revision: "0123456789abcdef"
    hash_prefix: "a1b2c3d4"
    voices:
      - name: clone
"""
        )

        storage = YamlDataStorage(str(config_yml))
        model_info = storage.get_model_info("qwen3_tts")

        assert model_info.revision == "0123456789abcdef"
        assert model_info.hash_prefix == "a1b2c3d4"


class TestDisabledModelInfo:
    """Tests for Model Info disabling via enabled=False."""

    def test_disabled_model_info_voices_excluded_from_get_voices(self):
        """get_voices should exclude voices that reference a disabled Model Info."""

        config_model = PredefinedData(
            models=[
                make_model_info(enabled=False),
                make_model_info(id="v3_en", enabled=True),
            ],
            voices=[
                Voice(
                    id="v5_6_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model_id="v5_6_ru",
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
        assert not any(v.model_id == "v5_6_ru" for v in result)
        assert any(v.model_id == "v3_en" for v in result)
        assert any(v.name == "en_0" for v in result)

    def test_disabled_model_info_get_model_info_returns_none(self):
        """get_model_info should return None for a disabled Model Info."""

        config_model = PredefinedData(
            models=[
                make_model_info(enabled=False),
            ],
            voices=[],
        )

        storage = YamlDataStorage(config_model)

        assert storage.get_model_info("v5_6_ru") is None


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
  v5_6_ru:
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
        vn = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru")
        assert vn is not None
        assert vn.voice_id == "v5_6_ru-aidar"
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
  v5_6_ru:
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
        assert storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "en") is None

    def test_get_voice_normalization_multiple_languages(self, tmp_path):
        """get_voice_normalization distinguishes overrides for different languages."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
        ru_vn = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru")
        en_vn = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "en")
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
  v5_6_ru:
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
        vn = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru")
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
  v5_6_ru:
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
  v5_6_ru:
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
        assert storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.SSML, "ru") is None

    def test_get_voice_normalization_voice_without_normalization(self, tmp_path):
        """get_voice_normalization returns None when voice has no normalization section."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru") is None

    def test_get_voice_normalization_disabled_entry(self, tmp_path):
        """get_voice_normalization returns entry even if enabled=False."""
        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
        vn = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru")
        assert vn is not None
        assert vn.enabled is False
        assert vn.type == NormalizationType.SIMPLE


class TestModelInfoCapabilities:
    """Tests for parsing and validating Model Info capability fields from YAML."""

    def test_missing_languages_raises_value_error(self, tmp_path):
        """A Model Info without a languages list fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
            ("qwen3", EngineType.QWEN3),
            ("openai", EngineType.OPENAI),
        ],
    )
    def test_engine_type_maps_to_enum(self, tmp_path, yaml_value, expected):
        """engine_type maps the YAML name to the EngineType member."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            f"""
models:
  v5_6_ru:
    engine_type: {yaml_value}
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").engine_type is expected

    def test_missing_engine_type_raises_value_error(self, tmp_path):
        """A Model Info without engine_type fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
  v5_6_ru:
    engine_type: klingon
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError, match="engine_type"):
            YamlDataStorage(str(config_yml))

    def test_the_old_qwen_spelling_is_rejected_with_the_valid_families_named(self, tmp_path):
        """`qwen` is no longer a family, and the error says which families are."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: qwen
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        with pytest.raises(ValueError) as exc_info:
            YamlDataStorage(str(config_yml))

        message = str(exc_info.value)
        assert "qwen3" in message
        assert "silero" in message
        assert "openai" in message

    def test_languages_parse_as_trimmed_list(self, tmp_path):
        """languages parses into a list with each entry whitespace-trimmed."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages:
      - " ru "
      - "  en"
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))

        assert storage.get_model_info("v5_6_ru").languages == ["ru", "en"]

    def test_empty_languages_raises_value_error(self, tmp_path):
        """An explicitly empty languages list fails fast at load."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
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
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))
        model_info = storage.get_model_info("v5_6_ru")

        assert model_info.ssml_supported is False
        assert model_info.language_auto_detected is False

    def test_ssml_supported_and_language_auto_detected_parse_true(self, tmp_path):
        """Declared true ssml_supported and language_auto_detected parse as true."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    ssml_supported: true
    language_auto_detected: true
    voices:
      - name: aidar
"""
        )

        storage = YamlDataStorage(str(config_yml))
        model_info = storage.get_model_info("v5_6_ru")

        assert model_info.ssml_supported is True
        assert model_info.language_auto_detected is True


class TestActiveModelsAllowlist:
    """Tests for the active_models runtime allowlist."""

    def test_active_model_is_served(self):
        """A model listed in active_models and enabled is served; unlisted models' voices are dropped."""
        config_model = PredefinedData(
            models=[
                make_model_info(),
                make_model_info(id="v3_en"),
            ],
            voices=[
                Voice(id="v5_6_ru-aidar", name="aidar", speaker="aidar", model_id="v5_6_ru"),
                Voice(id="v3_en-en_0", name="en_0", speaker="en_0", model_id="v3_en"),
            ],
        )

        storage = YamlDataStorage(config_model, active_models=["v5_6_ru"])

        assert storage.get_model_info("v5_6_ru") is not None
        assert storage.get_model_info("v3_en") is None
        assert not any(v.model_id == "v3_en" for v in storage.get_voices())

    def test_listed_but_disabled_model_is_not_served_and_warns(self):
        """A model listed in active_models but disabled is not served and logs a warning."""
        config_model = PredefinedData(
            models=[
                make_model_info(),
                make_model_info(id="v3_en", enabled=False),
            ],
            voices=[
                Voice(id="v5_6_ru-aidar", name="aidar", speaker="aidar", model_id="v5_6_ru"),
                Voice(id="v3_en-en_0", name="en_0", speaker="en_0", model_id="v3_en"),
            ],
        )

        sink = io.StringIO()
        handler = logger.add(sink, level="WARNING")
        try:
            storage = YamlDataStorage(config_model, active_models=["v5_6_ru", "v3_en"])
        finally:
            logger.remove(handler)

        assert storage.get_model_info("v3_en") is None
        assert not any(v.model_id == "v3_en" for v in storage.get_voices())
        assert "v3_en" in sink.getvalue()


class TestInputsTheShapesAllow:
    """Inputs a Model Info or a Voice can carry, which were rejected on the way in."""

    def test_a_path_is_read_as_written(self, tmp_path):
        """The storage invites a Path in its signature, and used to raise on one.

        Passing a string worked, which is why nothing caught it: every other test hands
        over a string too.
        """
        path = write_data_file(tmp_path, MODEL_WITH_VOICE)

        storage = YamlDataStorage(path)

        assert storage.get_voice("v5_6_ru-aidar").name == "aidar"

    def test_a_null_speaker_falls_back_to_the_voice_name(self, tmp_path):
        """An explicit null means the same as leaving the speaker out.

        The fallback exists for an absent speaker; written as null it used to raise
        instead, because the fallback reached strip() on None.
        """
        path = write_data_file(
            tmp_path,
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        speaker: null
""",
        )

        storage = YamlDataStorage(path)

        assert storage.get_voice("v5_6_ru-aidar").speaker == "aidar"

    @pytest.mark.parametrize("section", ["models", "prompts"])
    def test_an_empty_section_is_read_as_absent(self, tmp_path, section):
        """A section written as null is a section with nothing in it, not a crash."""
        contents = (
            MODEL_WITH_VOICE if section == "models" else f"{MODEL_WITH_VOICE}\n{section}: null\n"
        )
        path = write_data_file(tmp_path, contents)

        storage = YamlDataStorage(path)

        assert storage.get_model_infos() if section == "models" else storage.get_voices()

    def test_null_voices_are_no_voices(self, tmp_path):
        """A Model Info may carry no voices at all, and saying so explicitly is allowed."""
        path = write_data_file(
            tmp_path,
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices: null
""",
        )

        storage = YamlDataStorage(path)

        assert storage.get_voice("v5_6_ru-aidar") is None
        assert storage.get_model_info("v5_6_ru") is not None

    def test_a_voice_without_a_name_is_refused_by_name(self, tmp_path):
        """A name is required, so it is refused — but by something a reader can act on."""
        path = write_data_file(
            tmp_path,
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - speaker: aidar
""",
        )

        with pytest.raises(ValueError) as exc_info:
            YamlDataStorage(path)

        assert "v5_6_ru" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("contents", "expected"),
        [
            pytest.param("models:\n  v5_6_ru:\n", "v5_6_ru", id="model-with-no-body"),
            pytest.param(
                "models:\n  v5_6_ru:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      - null\n",
                "v5_6_ru",
                id="voice-entry-that-is-null",
            ),
            pytest.param(
                "models:\n  v5_6_ru:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      - aidar\n",
                "v5_6_ru",
                id="voice-entry-that-is-not-a-mapping",
            ),
        ],
    )
    def test_a_wrong_shape_inside_a_model_is_refused_by_name(self, tmp_path, contents, expected):
        """A mistyped entry is refused with something a reader can act on.

        All three used to raise a bare AttributeError or TypeError from inside the
        parser, naming nothing about the file that was wrong.
        """
        path = write_data_file(tmp_path, contents)

        with pytest.raises(ValueError) as exc_info:
            YamlDataStorage(path)

        assert expected in str(exc_info.value)

    @pytest.mark.parametrize(
        "contents",
        [
            pytest.param("- one\n- two\n", id="a-list"),
            pytest.param("models: v5_6_ru\n", id="models-is-not-a-mapping"),
            pytest.param("prompts:\n  id: ru_text\n", id="prompts-is-not-a-list"),
        ],
    )
    def test_a_data_file_of_the_wrong_shape_is_refused_by_name(self, tmp_path, contents):
        """The document itself has to be a mapping of the sections the parser reads."""
        path = write_data_file(tmp_path, contents)

        with pytest.raises(ValueError) as exc_info:
            YamlDataStorage(path)

        assert "data.yml" in str(exc_info.value), "the error must name the file that was wrong"

    @pytest.mark.parametrize(
        ("contents", "expected"),
        [
            pytest.param("prompts:\n  - text: hi\n    model: m\n", "id", id="prompt-without-an-id"),
            pytest.param("prompts:\n  - null\n", "prompts", id="prompt-that-is-null"),
            pytest.param("prompts:\n  - a string\n", "prompts", id="prompt-that-is-a-string"),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      - name: aidar\n        normalization: ru\n",
                "normalization",
                id="normalization-that-is-not-a-mapping",
            ),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      - name: aidar\n        normalization:\n"
                "          ru:\n            text: simple\n",
                "normalization",
                id="normalization-without-a-mapping-per-language",
            ),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: ru\n",
                "languages",
                id="languages-written-as-a-string",
            ),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: [1]\n",
                "languages",
                id="language-that-is-not-a-string",
            ),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      - name: null\n",
                "name",
                id="voice-name-that-is-null",
            ),
            pytest.param(
                "models:\n  m:\n    engine_type: silero\n    languages: [ru]\n"
                "    voices:\n      aidar: {}\n",
                "voices",
                id="voices-that-are-not-a-list",
            ),
        ],
    )
    def test_a_shape_the_data_file_does_not_allow_is_refused_by_name(
        self, tmp_path, contents, expected
    ):
        """A value written in the wrong shape is refused, not read into nothing.

        Each of these used to raise a bare KeyError, TypeError or AttributeError from
        inside the parser, or to be silently dropped: a mistyped data file should say
        what is wrong with it, in terms the reader wrote it in.
        """
        path = write_data_file(tmp_path, contents)

        with pytest.raises(ValueError) as exc_info:
            YamlDataStorage(path)

        assert expected in str(exc_info.value)

    def test_a_language_list_of_strings_is_read_as_written(self, tmp_path):
        """The shape the parser accepts is the shape it reads, unchanged."""
        path = write_data_file(
            tmp_path,
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru, en]
""",
        )

        storage = YamlDataStorage(path)

        assert storage.get_model_info("v5_6_ru").languages == ["ru", "en"]

    def test_a_normalization_block_written_as_documented_is_read(self, tmp_path):
        """A correctly shaped override survives; only the malformed ones are refused."""
        path = write_data_file(
            tmp_path,
            """
models:
  v5_6_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: ru_text
prompts:
  - id: ru_text
    text: "Normalize Russian text"
    model: qwen3.5:4b
""",
        )

        storage = YamlDataStorage(path)

        override = storage.get_voice_normalization("v5_6_ru-aidar", TextFormat.TEXT, "ru")

        assert override.type.value == "openai"
        assert override.enabled is True
        assert storage.get_prompt("ru_text").model == "qwen3.5:4b"
