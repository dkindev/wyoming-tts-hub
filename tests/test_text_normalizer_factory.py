import unittest.mock
from pathlib import Path

import pytest
import yaml

from src.config import (
    NormalizationPrompt,
    NormalizationSettings,
    TextFormatNormalizationSettings,
)
from src.tts.data_storage import YamlDataStorage
from src.tts.models import NormalizationType, Prompt, TextFormat, VoiceNormalization
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    SsmlNormalizer,
    TextNormalizerFactory,
    unreachable_normalization_prompts,
)
from tests.helpers import FakeDataStorage, make_merged_yaml, make_model_info, make_voice

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


class TestUnreachableNormalizationPrompts:
    """A prompt no served Model Info declares is reported rather than sitting unused."""

    def test_a_prompt_for_a_served_language_is_not_reported(self):
        storage = FakeDataStorage(models=[make_model_info(languages=["ru"])])
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru": NormalizationPrompt(text="t", model="m")}
            )
        )

        assert unreachable_normalization_prompts(settings, storage) == {}

    def test_a_prompt_keyed_by_a_locale_is_reported(self):
        storage = FakeDataStorage(models=[make_model_info(languages=["ru"])])
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru_RU": NormalizationPrompt(text="t", model="m")}
            )
        )

        assert unreachable_normalization_prompts(settings, storage) == {"text": {"ru_RU"}}

    def test_it_is_reported_per_text_format(self):
        storage = FakeDataStorage(models=[make_model_info(languages=["ru"])])
        prompt = NormalizationPrompt(text="t", model="m")
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(prompts={"ru": prompt}),
            ssml=TextFormatNormalizationSettings(prompts={"en_US": prompt}),
        )

        assert unreachable_normalization_prompts(settings, storage) == {"ssml": {"en_US"}}

    def test_no_prompts_reports_nothing(self):
        storage = FakeDataStorage(models=[make_model_info(languages=["ru"])])

        assert unreachable_normalization_prompts(NormalizationSettings(), storage) == {}

    def test_a_prompt_for_a_model_this_instance_does_not_serve_is_reported(self, tmp_path):
        """The report is about what is served, so a staged prompt is still reported.

        A Language can be declared by a Model Info the instance does not serve, which
        leaves the prompt written but unselected until that Model Info is activated.
        """

        path = make_merged_yaml(
            tmp_path,
            {
                "v5_5_ru": {"engine_type": "silero", "languages": ["ru"], "voices": []},
                "v3_en": {"engine_type": "silero", "languages": ["en"], "voices": []},
            },
        )
        storage = YamlDataStorage(config_path_or_model=path, active_models=["v5_5_ru"])
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={
                    "ru": NormalizationPrompt(text="t", model="m"),
                    "en": NormalizationPrompt(text="t", model="m"),
                }
            )
        )

        assert unreachable_normalization_prompts(settings, storage) == {"text": {"en"}}

    def test_the_shipped_configuration_has_no_unreachable_prompt(self):
        """The configuration the project ships would start without a warning."""
        storage = YamlDataStorage(
            config_path_or_model=str(REPO_ROOT / "data" / "data.yml"),
            active_models=shipped_config()["active_models"],
        )
        normalization = shipped_config()["normalization"]

        assert (
            unreachable_normalization_prompts(
                NormalizationSettings(
                    text=TextFormatNormalizationSettings(**normalization["text"]),
                    ssml=TextFormatNormalizationSettings(**normalization["ssml"]),
                ),
                storage,
            )
            == {}
        )
