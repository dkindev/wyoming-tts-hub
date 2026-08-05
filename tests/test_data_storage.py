from src.tts.data_storage import YamlDataStorage
from src.tts.models import Model, NormalizationType, PredefinedData, TextFormat, Voice


class TestYamlDataStorageInit:
    """Tests for SileroTTSYamlConfigStorage initialization."""

    def test_init_accepts_config_model(self):
        """Should accept TTSConfigModel and expose get_voice."""

        config_model = PredefinedData(
            models=[Model(id="v5_5_ru", language="ru")],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                )
            ],
        )

        storage = YamlDataStorage(config_model)

        assert storage.get_voice("ru_RU-v5_5_ru-aidar").name == "aidar"


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
            models=[Model(id="v5_5_ru", language="ru")],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 1
        assert result[0].id == "ru_RU-v5_5_ru-aidar"
        assert result[0].locale == "ru_RU"

    def test_get_voices_includes_all_voices(self):
        """get_voices should include all voices."""

        config_model = PredefinedData(
            models=[Model(id="v5_5_ru", language="ru")],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                ),
                Voice(
                    id="ru_RU-v5_5_ru-baya",
                    name="baya",
                    speaker="baya",
                    model="v5_5_ru",
                    locale="ru_RU",
                ),
            ],
        )
        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert len(result) == 2
        assert result[0].name == "aidar"
        assert result[1].name == "baya"

    def test_get_voices_from_all_locales(self):
        """get_voices should include voices from all locales."""

        config_model = PredefinedData(
            models=[Model(id="v5_5_ru", language="ru"), Model(id="v3_en", language="en")],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                ),
                Voice(
                    id="en_US-v3_en-en_0",
                    name="en_0",
                    speaker="en_0",
                    model="v3_en",
                    locale="en_US",
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
            models=[Model(id="v5_5_ru", language="ru")],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                )
            ],
        )
        storage = YamlDataStorage(config_model)

        voice = storage.get_voice("ru_RU-v5_5_ru-aidar")
        assert voice.speaker == "aidar"
        assert voice.model == "v5_5_ru"


class TestYamlConstructor:
    """Tests for constructing from a YAML file path."""

    def test_loads_config_from_yaml_path(self, tmp_path):
        """Should load config from a YAML file path with merged structure."""

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

        voice = storage.get_voice("ru_RU-v5_5_ru-aidar")
        assert voice.name == "aidar"
        assert voice.speaker == "aidar"
        assert voice.model == "v5_5_ru"

    def test_loaded_voices_have_voice_configs(self, tmp_path):
        """get_voices should return Voice objects with computed id."""

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

        voices = storage.get_voices()
        assert len(voices) == 1
        assert voices[0].id == "ru_RU-v5_5_ru-aidar"
        assert voices[0].locale == "ru_RU"

    def test_missing_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML without speaker field should default speaker to voice_name."""

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
            model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("ru_RU-v5_5_ru-aidar")
        assert voice.speaker == "aidar"

    def test_empty_speaker_defaults_to_voice_name(self, tmp_path):
        """YAML with speaker: '' should default speaker to voice_name."""

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
            speaker: ""
            model: v5_5_ru
"""
        )

        storage = YamlDataStorage(str(config_yml))
        voice = storage.get_voice("ru_RU-v5_5_ru-aidar")
        assert voice.speaker == "aidar"


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
    language: ru
    enabled: false
    locales:
      ru_RU:
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

        assert len(storage.get_voices()) == 1

    def test_yaml_enabled_true_explicitly_enables_model(self, tmp_path):
        """YAML with enabled: true should keep the model enabled."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    language: ru
    enabled: true
    locales:
      ru_RU:
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
    language: ru
    enabled: false
    locales:
      ru_RU:
        voices:
          - name: aidar
            speaker: aidar
            model: v5_5_ru
  v3_en:
    language: en
    enabled: true
    locales:
      en_US:
        voices:
          - name: en_0
            speaker: en_0
            model: v3_en
"""
        )

        storage = YamlDataStorage(str(config_yml))

        voices = storage.get_voices()
        assert not any(v.locale == "ru_RU" for v in voices)
        assert any(v.locale == "en_US" for v in voices)
        assert any(v.name == "en_0" for v in voices)


class TestGetModel:
    """Tests for get_model() method."""

    def test_get_model_returns_correct_model(self):
        """get_model should return Model for the given model name."""

        config_model = PredefinedData(
            models=[Model(id="v5_5_ru", language="ru")],
            voices=[],
        )
        storage = YamlDataStorage(config_model)

        m = storage.get_model("v5_5_ru")
        assert m.language == "ru"


class TestGetModels:
    def test_get_models_returns_all_enabled_models(self):
        """get_models() returns list of all enabled Model objects."""

        config_model = PredefinedData(
            models=[
                Model(id="v5_5_ru", language="ru", warmup=True),
                Model(id="v3_en", language="en"),
            ],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
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
    language: ru
    warmup: true
    locales:
      ru_RU:
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
    language: ru
    hash_prefix: "a1b2c3d4"
    locales:
      ru_RU:
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

        assert storage.get_model("v5_5_ru").hash_prefix is None

    def test_yaml_empty_hash_prefix_defaults_to_none(self, tmp_path):
        """YAML with empty hash_prefix should default to None."""

        config_yml = tmp_path / "config.yml"
        config_yml.write_text(
            """
models:
  v5_5_ru:
    language: ru
    hash_prefix: ""
    locales:
      ru_RU:
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
                Model(id="v5_5_ru", language="ru", enabled=False),
                Model(id="v3_en", language="en", enabled=True),
            ],
            voices=[
                Voice(
                    id="ru_RU-v5_5_ru-aidar",
                    name="aidar",
                    speaker="aidar",
                    model="v5_5_ru",
                    locale="ru_RU",
                ),
                Voice(
                    id="en_US-v3_en-en_0",
                    name="en_0",
                    speaker="en_0",
                    model="v3_en",
                    locale="en_US",
                ),
            ],
        )

        storage = YamlDataStorage(config_model)

        result = storage.get_voices()
        assert not any(v.locale == "ru_RU" for v in result)
        assert any(v.locale == "en_US" for v in result)
        assert any(v.name == "en_0" for v in result)

    def test_disabled_model_get_model_returns_none(self):
        """get_model should return None for a disabled model."""

        config_model = PredefinedData(
            models=[
                Model(id="v5_5_ru", language="ru", enabled=False),
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
        """get_voice_normalization should return VoiceNormalization for voice + text_format."""
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
            normalization:
              text:
                enabled: true
                type: llm
                prompt_id: p1
"""
        )
        storage = YamlDataStorage(str(config_yml))
        vn = storage.get_voice_normalization("ru_RU-v5_5_ru-aidar", TextFormat.TEXT)
        assert vn is not None
        assert vn.voice_id == "ru_RU-v5_5_ru-aidar"
        assert vn.text_format == TextFormat.TEXT
        assert vn.type == NormalizationType.LLM
        assert vn.enabled is True
        assert vn.prompt_id == "p1"

    def test_get_voice_normalization_returns_none_for_unknown_voice(self, tmp_path):
        """get_voice_normalization returns None for unknown voice_id."""
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
            normalization:
              text:
                enabled: true
                type: llm
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("unknown-voice", TextFormat.TEXT) is None

    def test_get_voice_normalization_returns_none_for_unknown_format(self, tmp_path):
        """get_voice_normalization returns None for text_format not in normalization."""
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
            normalization:
              text:
                enabled: true
                type: llm
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("ru_RU-v5_5_ru-aidar", TextFormat.SSML) is None

    def test_get_voice_normalization_voice_without_normalization(self, tmp_path):
        """get_voice_normalization returns None when voice has no normalization section."""
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
"""
        )
        storage = YamlDataStorage(str(config_yml))
        assert storage.get_voice_normalization("ru_RU-v5_5_ru-aidar", TextFormat.TEXT) is None

    def test_get_voice_normalization_disabled_entry(self, tmp_path):
        """get_voice_normalization returns entry even if enabled=False."""
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
            normalization:
              text:
                enabled: false
                type: simple
"""
        )
        storage = YamlDataStorage(str(config_yml))
        vn = storage.get_voice_normalization("ru_RU-v5_5_ru-aidar", TextFormat.TEXT)
        assert vn is not None
        assert vn.enabled is False
        assert vn.type == NormalizationType.SIMPLE
