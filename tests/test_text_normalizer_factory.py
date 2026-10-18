import unittest.mock
from pathlib import Path

import pytest
import yaml

from src.config import (
    NormalizationPrompt,
    NormalizationSettings,
    TextFormatNormalizationSettings,
)
from src.tts.models import NormalizationType, Prompt, TextFormat, VoiceNormalization
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    SsmlNormalizer,
    TextNormalizerFactory,
)
from tests.helpers import make_voice

REPO_ROOT = Path(__file__).resolve().parent.parent
"""The checkout the shipped configuration files live in."""


def shipped_config() -> dict:
    """The settings the project ships, as Settings would read them."""
    return yaml.safe_load((REPO_ROOT / "config.yml").read_text())


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


def llm_settings(prompts: dict[str, NormalizationPrompt]) -> NormalizationSettings:
    """Server-wide settings that normalize text through an LLM, with these prompts."""
    return NormalizationSettings(
        text=TextFormatNormalizationSettings(
            enabled=True,
            type=NormalizationType.OPENAI,
            prompts=prompts,
        ),
    )


class TestServerWidePromptByLanguage:
    """A server-wide prompt is selected by the Language a Model Info declares."""

    def test_prompt_keyed_by_the_language_is_selected(self, mock_openai_client, mock_storage):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=llm_settings(
                {"ru": NormalizationPrompt(text="спрячь цифры", model="ru-model")}
            ),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert isinstance(result, OpenAiTextNormalizer)
        assert result._model == "ru-model"
        assert result._promt == "спрячь цифры"

    def test_prompt_keyed_by_a_locale_is_not_selected(self, mock_openai_client, mock_storage):
        """A locale form is unreachable, because no request can resolve to one.

        Before, this was how the shipped Russian prompt was written, so the operator
        configured a prompt and got no LLM normalization and no error either.
        """
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=llm_settings(
                {"ru_RU": NormalizationPrompt(text="спрячь цифры", model="ru-model")}
            ),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert result is None

    def test_a_language_with_no_prompt_falls_back_to_the_default_normalizer(
        self, mock_openai_client, mock_storage
    ):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(
                text=TextFormatNormalizationSettings(
                    enabled=True,
                    prompts={"en": NormalizationPrompt(text="normalize", model="en-model")},
                ),
            ),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert isinstance(result, PlainTextNormalizer)

    def test_each_language_normalizes_with_its_own_prompt(self, mock_openai_client, mock_storage):
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=llm_settings(
                {
                    "ru": NormalizationPrompt(text="спрячь цифры", model="ru-model"),
                    "en": NormalizationPrompt(text="spell out digits", model="en-model"),
                }
            ),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        russian = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        english = factory.create(voice=voice, text_format=TextFormat.TEXT, language="en")

        assert russian._model == "ru-model"
        assert english._model == "en-model"

    def test_llm_with_no_prompt_for_the_language_normalizes_nothing(
        self, mock_openai_client, mock_storage
    ):
        """No prompt for this Language is not a failed request.

        The request proceeds with its text as written, which is what the middleware
        does with no normalizer at all.
        """
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=llm_settings({"en": NormalizationPrompt(text="normalize", model="en-model")}),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert result is None

    def test_a_voice_without_a_prompt_id_falls_back_to_the_language_prompt(
        self, mock_openai_client
    ):
        """An LLM-backed Voice that names no Prompt normalizes by the server-wide one."""
        storage = unittest.mock.MagicMock()
        storage.get_voice_normalization.return_value = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.OPENAI,
            enabled=True,
            prompt_id=None,
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=llm_settings(
                {"ru": NormalizationPrompt(text="спрячь цифры", model="ru-model")}
            ),
            storage=storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert isinstance(result, OpenAiTextNormalizer)
        assert result._model == "ru-model"
        storage.get_prompt.assert_not_called()

    def test_the_shipped_russian_prompt_is_reachable(self, mock_openai_client, mock_storage):
        """The prompt the project ships is found for the Language its Model Info declares.

        The shipped type is `simple`, so LLM normalization is opt-in; this says that
        opting in finds the prompt rather than silently finding nothing.
        """
        text_settings = dict(shipped_config()["normalization"]["text"])
        text_settings["type"] = "openai"
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(
                text=TextFormatNormalizationSettings(**text_settings),
            ),
            storage=mock_storage,
        )
        voice = make_voice(voice_id="v1", name="Test")

        result = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert isinstance(result, OpenAiTextNormalizer)
        assert result._model


class TestNormalizerReuse:
    """A normalizer is built once per Voice, Text Format and Language."""

    def factory(self, mock_storage, settings=None):
        return TextNormalizerFactory(
            openai_client=unittest.mock.MagicMock(),
            settings=settings
            or NormalizationSettings(
                text=TextFormatNormalizationSettings(enabled=True),
            ),
            storage=mock_storage,
        )

    def test_the_same_request_reuses_one_normalizer(self, mock_storage):
        factory = self.factory(mock_storage)
        voice = make_voice(voice_id="v1", name="Test")

        first = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        second = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")

        assert first is second

    def test_another_language_builds_its_own(self, mock_storage):
        factory = self.factory(mock_storage)
        voice = make_voice(voice_id="v1", name="Test")

        russian = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        english = factory.create(voice=voice, text_format=TextFormat.TEXT, language="en")

        assert russian is not english

    def test_another_text_format_builds_its_own(self, mock_storage):
        factory = self.factory(
            mock_storage,
            settings=NormalizationSettings(
                text=TextFormatNormalizationSettings(enabled=True),
                ssml=TextFormatNormalizationSettings(enabled=True),
            ),
        )
        voice = make_voice(voice_id="v1", name="Test")

        text = factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru")
        ssml = factory.create(voice=voice, text_format=TextFormat.SSML, language="ru")

        assert text is not ssml

    def test_one_voice_does_not_inherit_another_voices_prompt(self, mock_openai_client):
        """Two voices normalize by their own Prompt, not whichever was seen first."""
        storage = unittest.mock.MagicMock()
        storage.get_voice_normalization.side_effect = lambda voice_id, text_format, language: (
            VoiceNormalization(
                voice_id=voice_id,
                text_format=text_format,
                language=language,
                type=NormalizationType.OPENAI,
                enabled=True,
                prompt_id=f"prompt-{voice_id}",
            )
        )
        storage.get_prompt.side_effect = lambda prompt_id: Prompt(
            id=prompt_id, text=f"text of {prompt_id}", model="model"
        )
        factory = TextNormalizerFactory(
            openai_client=mock_openai_client,
            settings=NormalizationSettings(),
            storage=storage,
        )

        first = factory.create(
            voice=make_voice(voice_id="v1", name="Test"), text_format=TextFormat.TEXT, language="ru"
        )
        second = factory.create(
            voice=make_voice(voice_id="v2", name="Test"), text_format=TextFormat.TEXT, language="ru"
        )

        assert first._promt == "text of prompt-v1"
        assert second._promt == "text of prompt-v2"

    def test_a_disabled_normalizer_is_remembered_too(self):
        """A Voice switched off stays off, rather than being re-decided per request."""
        storage = unittest.mock.MagicMock()
        storage.get_voice_normalization.return_value = VoiceNormalization(
            voice_id="v1",
            text_format=TextFormat.TEXT,
            language="ru",
            type=NormalizationType.SIMPLE,
            enabled=False,
        )
        factory = self.factory(storage)
        voice = make_voice(voice_id="v1", name="Test")

        assert factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru") is None
        assert factory.create(voice=voice, text_format=TextFormat.TEXT, language="ru") is None
        assert storage.get_voice_normalization.call_count == 1
