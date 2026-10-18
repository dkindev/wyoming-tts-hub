from collections.abc import Callable

from loguru import logger
from openai import AsyncOpenAI

from src.config import (
    NormalizationPrompt,
    NormalizationSettings,
    TextFormatNormalizationSettings,
)
from src.tts.data_storage import DataStorage
from src.tts.models import (
    Prompt,
    TextFormat,
    Voice,
    VoiceNormalization,
)
from src.tts.preprocessing import (
    OpenAiTextNormalizer,
    PlainTextNormalizer,
    SsmlNormalizer,
    TextNormalizer,
)


def unreachable_normalization_prompts(
    settings: NormalizationSettings, storage: DataStorage
) -> dict[str, set[str]]:
    """Return the server-wide prompts no Model Info this instance serves declares.

    Maps a Text Format to the Languages its prompts are keyed by that no served Model
    Info declares. A prompt keyed any other way is written but never selected, because
    a request's Language is always one a Model Info declared — so this is where a
    spelling mistake surfaces, at startup, rather than as text that silently came
    back unnormalized.

    Only Model Infos the instance serves are consulted: a Language declared by one it
    does not serve leaves its prompt unused until that Model Info is activated, which
    is a staged configuration rather than a mistake.
    """
    declared = {
        language for model_info in storage.get_model_infos() for language in model_info.languages
    }

    unreachable: dict[str, set[str]] = {}
    for text_format, format_settings in (("text", settings.text), ("ssml", settings.ssml)):
        if not format_settings.prompts:
            continue

        unreachable_languages = set(format_settings.prompts) - declared
        if unreachable_languages:
            unreachable[text_format] = unreachable_languages

    return unreachable


class TextNormalizerFactory:
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        settings: NormalizationSettings,
        storage: DataStorage,
    ):
        self._settings = settings
        self._storage = storage
        self._openai_client = openai_client

        def _create_openai_normalizer(
            voice: Voice,
            voice_normalization: VoiceNormalization | None,
            settings: TextFormatNormalizationSettings,
            language: str,
        ) -> TextNormalizer | None:
            if self._openai_client is None:
                return None

            prompt: Prompt | NormalizationPrompt | None = (
                self._storage.get_prompt(prompt_id=voice_normalization.prompt_id)
                if voice_normalization is not None and voice_normalization.prompt_id
                else None
            ) or self._prompt_for_language(settings=settings, language=language)

            if prompt is None:
                return None

            return OpenAiTextNormalizer(
                client=self._openai_client, model=prompt.model, promt=prompt.text
            )

        self._builders: dict[
            str,
            Callable[
                [Voice, VoiceNormalization | None, TextFormatNormalizationSettings, str],
                TextNormalizer | None,
            ],
        ] = {
            # key: "{text_format}__{normalization_type}"
            "text__simple": lambda v, vn, s, language: PlainTextNormalizer(),
            "ssml__simple": lambda v, vn, s, language: SsmlNormalizer(),
            "text__openai": _create_openai_normalizer,
            "ssml__openai": _create_openai_normalizer,
        }

    def _prompt_for_language(
        self, settings: TextFormatNormalizationSettings, language: str
    ) -> NormalizationPrompt | None:
        """Return the server-wide Prompt written for a Language, if there is one.

        Prompts are keyed by the Language a Model Info declares, which is the only
        Language a request can resolve to — so this is an exact match on that
        Language, and nothing else finds the Prompt. A key written any other way is
        unreachable, which `unreachable_normalization_prompts` reports at startup.
        """
        if not settings.prompts:
            return None

        return settings.prompts.get(language)

    def create(self, voice: Voice, text_format: TextFormat, language: str) -> TextNormalizer | None:
        if voice is None:
            raise TypeError("voice cannot be None")

        if language is None:
            raise TypeError("language cannot be None")

        settings = self._settings.text if text_format is TextFormat.TEXT else self._settings.ssml

        voice_normalization = self._storage.get_voice_normalization(
            voice_id=voice.id, text_format=text_format, language=language
        )
        if voice_normalization is not None:
            if not voice_normalization.enabled:
                return None

            normalization_type = voice_normalization.type
        else:
            if not settings.enabled:
                return None

            normalization_type = settings.type

        builder = self._builders.get(f"{text_format.value}__{normalization_type.value}")
        if builder is None:
            logger.warning(
                "Text normalizer not found in factory. Language: {language}. "
                "Format: {format}. Type: {type}",
                language=language,
                format=text_format.value,
                type=normalization_type.value,
            )
            return None

        return builder(voice, voice_normalization, settings, language)
