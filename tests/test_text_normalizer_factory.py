import unittest.mock

import pytest

from src.config import (
    NormalizationSettings,
    SsmlNormalizationSettings,
    TextNormalizationSettings,
)
from src.tts.models import NormalizationType, Prompt, TextFormat, VoiceNormalization
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    SsmlNormalizer,
    TextNormalizerFactory,
)
from tests.helpers import make_voice


class TestTextNormalizerFactory:
    """Tests for TextNormalizerFactory.create_text_normalizer behavior."""

    def test_text_simple_returns_plain_text_normalizer(
        self, default_normalization_settings, mock_openai_client, mock_storage
    ):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert isinstance(result, PlainTextNormalizer)

    def test_ssml_simple_returns_ssml_normalizer(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            ssml=SsmlNormalizationSettings(enabled=True),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.SSML)
        assert isinstance(result, SsmlNormalizer)

    def test_text_llm_returns_openai_normalizer(self, mock_openai_client, mock_storage):
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="prompt1",
        )
        mock_storage.get_voice_normalization.return_value = vn
        prompt = Prompt(id="prompt1", text="normalize", model="gpt-4o-mini")
        mock_storage.get_prompt.return_value = prompt

        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert isinstance(result, OpenAiTextNormalizer)

    def test_text_llm_no_prompt_returns_none(self, mock_openai_client, mock_storage):
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="missing",
        )
        mock_storage.get_voice_normalization.return_value = vn
        mock_storage.get_prompt.return_value = None

        settings = NormalizationSettings(
            text=TextNormalizationSettings(prompts={}),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert result is None

    def test_text_llm_no_client_returns_none(self, default_normalization_settings):
        mock_storage = unittest.mock.MagicMock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="prompt1",
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=None,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert result is None

    def test_raises_type_error_for_none_voice(
        self, default_normalization_settings, mock_openai_client, mock_storage
    ):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        with pytest.raises(TypeError):
            factory.create_text_normalizer(voice=None, format=TextFormat.TEXT)

    def test_text_normalization_disabled_returns_none(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextNormalizationSettings(enabled=False),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert result is None

    def test_ssml_normalization_disabled_returns_none(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            ssml=SsmlNormalizationSettings(enabled=False),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.SSML)
        assert result is None

    def test_llm_with_none_prompts_returns_none(self, mock_storage):
        settings = NormalizationSettings(
            text=TextNormalizationSettings(
                type=NormalizationType.OPENAI,
                prompts=None,
            ),
        )
        factory = TextNormalizerFactory(openai_client=None, settings=settings, storage=mock_storage)
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert result is None


class TestTextNormalizerFactoryVoiceNormalization:
    """Tests for VoiceNormalization integration."""

    def test_voice_normalization_disabled_returns_none(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.SIMPLE,
            enabled=False,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert result is None

    def test_voice_normalization_simple_text_returns_plain_text_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.SIMPLE,
            enabled=True,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert isinstance(result, PlainTextNormalizer)

    def test_voice_normalization_simple_ssml_returns_ssml_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.SSML,
            type=NormalizationType.SIMPLE,
            enabled=True,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.SSML)
        assert isinstance(result, SsmlNormalizer)

    def test_voice_normalization_llm_returns_openai_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="prompt1",
        )
        mock_storage.get_voice_normalization.return_value = vn
        prompt = Prompt(id="prompt1", text="normalize", model="gpt-4o-mini")
        mock_storage.get_prompt.return_value = prompt
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert isinstance(result, OpenAiTextNormalizer)

    def test_no_voice_normalization_falls_through(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        mock_storage.get_voice_normalization.return_value = None
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test", locale="ru_RU")
        result = factory.create_text_normalizer(voice=voice, format=TextFormat.TEXT)
        assert isinstance(result, PlainTextNormalizer)
