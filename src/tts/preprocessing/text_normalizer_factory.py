from collections.abc import Callable

from loguru import logger
from openai import AsyncOpenAI

from src.config import NormalizationSettings, TextFormatNormalizationSettings
from src.tts.data_storage import DataStorage
from src.tts.models import (
    OpenAiNormalizationConfig,
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
            voice_normalization: VoiceNormalization,
            settings: TextFormatNormalizationSettings,
            language: str,
        ) -> TextNormalizer | None:
            if self._openai_client is None:
                return None

            prompt = (
                self._storage.get_prompt(prompt_id=voice_normalization.prompt_id)
                if voice_normalization is not None
                else None
            )

            if prompt is not None:
                prompt_text = prompt.text
                prompt_model = prompt.model
            else:
                if settings.prompts is None:
                    return None

                default_prompt = settings.prompts.get(language)
                if default_prompt is None:
                    return None

                prompt_text = default_prompt.text
                prompt_model = default_prompt.model

            return OpenAiTextNormalizer(
                client=self._openai_client,
                config=OpenAiNormalizationConfig(
                    timeout=self._settings.timeout,
                    max_concurrent_sentences_per_request=self._settings.max_concurrent_sentences_per_request,
                    default_model=prompt_model,
                    default_prompt=prompt_text,
                ),
            )

        self._builders: dict[
            str,
            Callable[
                [Voice, VoiceNormalization, TextFormatNormalizationSettings, str],
                TextNormalizer,
            ],
        ] = {
            # key: "{language}__{text_format}__{normalization_type}"
            "default__text__simple": lambda v, vn, s, language: PlainTextNormalizer(),
            "default__ssml__simple": lambda v, vn, s, language: SsmlNormalizer(),
            "default__text__openai": _create_openai_normalizer,
            "default__ssml__openai": _create_openai_normalizer,
        }

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

        builder = self._builders.get(f"{language}__{text_format.value}__{normalization_type.value}")
        if builder is None:
            builder = self._builders.get(
                f"default__{text_format.value}__{normalization_type.value}"
            )

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
