from src.config import NormalizationSettings
from src.tts.data_storage import YamlDataStorage
from src.tts.models import TextFormat
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    TextNormalizerFactory,
)
from tests.helpers import make_voice

YAML_WITH_LLM_NORMALIZATION = """
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
                prompt_id: ru_text

prompts:
  - id: ru_text
    text: "Normalize Russian text"
    model: qwen3.5:4b
"""

YAML_WITH_DISABLED_NORMALIZATION = """
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
                type: llm
                prompt_id: ru_text

prompts:
  - id: ru_text
    text: "Normalize Russian text"
    model: qwen3.5:4b
"""

YAML_WITHOUT_NORMALIZATION = """
models:
  v5_5_ru:
    language: ru
    locales:
      ru_RU:
        voices:
          - name: aidar
"""


class TestE2EVoiceNormalizationLLM:
    """End-to-end: YAML with LLM normalization -> factory returns OpenAiTextNormalizer."""

    def test_llm_voice_normalization_returns_openai_normalizer(self, tmp_path, mock_openai_client):
        config_yml = tmp_path / "data.yml"
        config_yml.write_text(YAML_WITH_LLM_NORMALIZATION)

        storage = YamlDataStorage(str(config_yml))
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(),
            storage=storage,
        )

        voice = make_voice(
            voice_id="ru_RU-v5_5_ru-aidar",
            name="aidar",
            locale="ru_RU",
        )
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)

        assert isinstance(result, OpenAiTextNormalizer)


class TestE2EVoiceNormalizationDisabled:
    """End-to-end: YAML with enabled:false -> factory returns None."""

    def test_disabled_normalization_returns_none(self, tmp_path, mock_openai_client):
        config_yml = tmp_path / "data.yml"
        config_yml.write_text(YAML_WITH_DISABLED_NORMALIZATION)

        storage = YamlDataStorage(str(config_yml))
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(),
            storage=storage,
        )

        voice = make_voice(
            voice_id="ru_RU-v5_5_ru-aidar",
            name="aidar",
            locale="ru_RU",
        )
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)

        assert result is None


class TestE2ENoVoiceNormalizationFallsThrough:
    """End-to-end: voice without normalization -> falls back to system defaults."""

    def test_no_normalization_uses_system_default(self, tmp_path, mock_openai_client):
        config_yml = tmp_path / "data.yml"
        config_yml.write_text(YAML_WITHOUT_NORMALIZATION)

        storage = YamlDataStorage(str(config_yml))
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(),
            storage=storage,
        )

        voice = make_voice(
            voice_id="ru_RU-v5_5_ru-aidar",
            name="aidar",
            locale="ru_RU",
        )
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)

        assert isinstance(result, PlainTextNormalizer)
