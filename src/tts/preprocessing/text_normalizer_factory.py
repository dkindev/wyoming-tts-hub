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


class TextNormalizerFactory:
    """Builds the Text Normalizer a request needs, once per Voice and Language.

    Normalizers are held onto because what they normalize with is fixed by
    configuration: the Voice's override, or the server-wide settings for its Text
    Format. Nothing is re-read between requests, so a second request for the same
    Voice, Text Format and Language can be handed the normalizer already built.
    """

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        settings: NormalizationSettings,
        storage: DataStorage,
    ):
        self._settings = settings
        self._storage = storage
        self._openai_client = openai_client
        self._normalizers: dict[tuple[str, str, str], TextNormalizer | None] = {}

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
        Language a request can resolve to. A prompt written under any other spelling
        is unreachable, so a miss is reported rather than left to look like a Voice
        that needs no normalization.
        """
        if not settings.prompts:
            return None

        prompt = settings.prompts.get(language)
        if prompt is None:
            logger.warning(
                "No normalization prompt for Language '{language}'. Prompts are keyed by a "
                "Language a Model Info declares, so one written with a region suffix — "
                "'ru_RU' rather than 'ru' — is never selected. Configured Languages: "
                "{configured}",
                language=language,
                configured=sorted(settings.prompts),
            )

        return prompt

    def create(self, voice: Voice, text_format: TextFormat, language: str) -> TextNormalizer | None:
        if voice is None:
            raise TypeError("voice cannot be None")

        if language is None:
            raise TypeError("language cannot be None")

        # The Voice is part of the key because an LLM-backed normalizer is built from
        # that Voice's Prompt, so a cache without it would hand one Voice's Prompt to
        # another. A Language is part of it because the server-wide prompts are keyed
        # by Language. The key is a tuple rather than joined text, so that a Voice id
        # or Language carrying the separator cannot collide with another.
        cache_key = (voice.id, text_format.value, language)
        if cache_key not in self._normalizers:
            self._normalizers[cache_key] = self._create(
                voice=voice, text_format=text_format, language=language
            )

        return self._normalizers[cache_key]

    def _create(
        self, voice: Voice, text_format: TextFormat, language: str
    ) -> TextNormalizer | None:
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
