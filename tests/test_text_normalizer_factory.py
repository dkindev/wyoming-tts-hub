import unittest.mock

import pytest

from src.config import NormalizationSettings, TextFormatNormalizationSettings
from src.tts.models import NormalizationType, Prompt, TextFormat, VoiceNormalization
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    SsmlNormalizer,
    TextNormalizerFactory,
)
from tests.helpers import make_voice


class TestTextNormalizerFactory:
    """Tests for TextNormalizerFactory.create behavior."""

    def test_text_simple_returns_plain_text_normalizer(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(enabled=True),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert isinstance(result, PlainTextNormalizer)

    def test_ssml_simple_returns_ssml_normalizer(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            ssml=TextFormatNormalizationSettings(enabled=True),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.SSML, language="ru")
        assert isinstance(result, SsmlNormalizer)

    def test_text_llm_returns_openai_normalizer(self, mock_openai_client, mock_storage):
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
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
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert isinstance(result, OpenAiTextNormalizer)

    def test_text_llm_no_prompt_returns_none(self, mock_openai_client, mock_storage):
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id="missing",
        )
        mock_storage.get_voice_normalization.return_value = vn
        mock_storage.get_prompt.return_value = None

        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(prompts={}),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert result is None

    def test_text_llm_no_client_returns_none(self, default_normalization_settings):
        mock_storage = unittest.mock.MagicMock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
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
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
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
            factory.create(voice=None, text_format=TextFormat.TEXT, language="ru")

    def test_raises_type_error_for_none_language(
        self, default_normalization_settings, mock_openai_client, mock_storage
    ):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        with pytest.raises(TypeError):
            factory.create(voice=voice, text_format=TextFormat.TEXT, language=None)

    def test_text_normalization_disabled_returns_none(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(enabled=False),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert result is None

    def test_ssml_normalization_disabled_returns_none(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            ssml=TextFormatNormalizationSettings(enabled=False),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.SSML, language="ru")
        assert result is None

    def test_llm_with_none_prompts_returns_none(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                enabled=True,
                type=NormalizationType.OPENAI,
                prompts=None,
            ),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert result is None

    def test_unknown_language_falls_back_to_default(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(enabled=True),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client, settings=settings, storage=mock_storage
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="en")
        assert isinstance(result, PlainTextNormalizer)


class TestTextNormalizerFactoryVoiceNormalization:
    """Tests for VoiceNormalization integration."""

    def test_voice_normalization_disabled_returns_none(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=False,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert result is None

    def test_voice_normalization_simple_text_returns_plain_text_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=True,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert isinstance(result, PlainTextNormalizer)

    def test_voice_normalization_simple_ssml_returns_ssml_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.SSML,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=True,
        )
        mock_storage.get_voice_normalization.return_value = vn
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.SSML, language="ru")
        assert isinstance(result, SsmlNormalizer)

    def test_voice_normalization_llm_returns_openai_normalizer(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        vn = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
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
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert isinstance(result, OpenAiTextNormalizer)

    def test_no_voice_normalization_falls_through(self, mock_openai_client, mock_storage):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(enabled=True),
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        assert isinstance(result, PlainTextNormalizer)

    def test_language_reaches_storage_lookup(
        self, default_normalization_settings, mock_openai_client
    ):
        mock_storage = unittest.mock.Mock()
        mock_storage.get_voice_normalization.return_value = None
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=default_normalization_settings,
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")
        factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        mock_storage.get_voice_normalization.assert_called_once_with(
            voice_id="v1", text_format=TextFormat.TEXT, language="ru"
        )
