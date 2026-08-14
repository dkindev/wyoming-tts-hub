from collections.abc import Callable

from src.tts.models import TextFormat
from src.tts.preprocessing import (
    PlainTextSentenizer,
    RuPlainTextSentenizer,
    SsmlSentenizer,
    TextSentenizer,
)


class TextSentenizerFactory:
    def __init__(self):
        self._builders: dict[str, Callable[[], TextSentenizer]] = {
            # key: "{language}__{text_format}"
            "default__text": PlainTextSentenizer,
            "default__ssml": lambda: SsmlSentenizer(text_sentenizer_in_tags=PlainTextSentenizer()),
            "ru__text": RuPlainTextSentenizer,
            "ru__ssml": lambda: SsmlSentenizer(text_sentenizer_in_tags=RuPlainTextSentenizer()),
        }

    def create(self, text_format: TextFormat, language: str | None = None) -> TextSentenizer:
        builder = self._builders.get(f"{language}__{text_format.value}")

        if builder is None:
            builder = self._builders.get(f"default__{text_format.value}")

        if builder is None:
            raise ValueError(f"No text sentenizer registered for format '{text_format.value}'")

        return builder()
