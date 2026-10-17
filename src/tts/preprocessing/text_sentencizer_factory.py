from collections.abc import Callable

from src.tts.models import TextFormat
from src.tts.preprocessing import (
    PlainTextSentencizer,
    RuPlainTextSentencizer,
    SsmlSentencizer,
    TextSentencizer,
)


class TextSentencizerFactory:
    def __init__(self):
        self._builders: dict[str, Callable[[], TextSentencizer]] = {
            # key: "{language}__{text_format}"
            "default__text": PlainTextSentencizer,
            "default__ssml": lambda: SsmlSentencizer(
                text_sentencizer_in_tags=PlainTextSentencizer()
            ),
            "ru__text": RuPlainTextSentencizer,
            "ru__ssml": lambda: SsmlSentencizer(text_sentencizer_in_tags=RuPlainTextSentencizer()),
        }

    def create(self, text_format: TextFormat, language: str | None = None) -> TextSentencizer:
        builder = self._builders.get(f"{language}__{text_format.value}")

        if builder is None:
            builder = self._builders.get(f"default__{text_format.value}")

        if builder is None:
            raise ValueError(f"No text sentencizer registered for format '{text_format.value}'")

        return builder()
