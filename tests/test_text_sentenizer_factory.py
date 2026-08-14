from src.tts.models import TextFormat
from src.tts.preprocessing import (
    PlainTextSentenizer,
    RuPlainTextSentenizer,
    SsmlSentenizer,
    TextSentenizerFactory,
)


class TestTextSentenizerFactory:
    """Tests for TextSentenizerFactory.create behavior."""

    def test_default_text_resolves_plain_text_sentenizer(self):
        factory = TextSentenizerFactory()
        sentenizer = factory.create(TextFormat.TEXT)
        assert isinstance(sentenizer, PlainTextSentenizer)

    def test_default_text_with_none_language_resolves_plain_text_sentenizer(self):
        factory = TextSentenizerFactory()
        sentenizer = factory.create(TextFormat.TEXT, None)
        assert isinstance(sentenizer, PlainTextSentenizer)

    def test_ru_text_resolves_ru_plain_text_sentenizer(self):
        factory = TextSentenizerFactory()
        sentenizer = factory.create(TextFormat.TEXT, "ru")
        assert isinstance(sentenizer, RuPlainTextSentenizer)

    def test_unknown_language_falls_back_to_default_text(self):
        factory = TextSentenizerFactory()
        sentenizer = factory.create(TextFormat.TEXT, "en")
        assert isinstance(sentenizer, PlainTextSentenizer)

    def test_unknown_language_falls_back_to_default_ssml(self):
        factory = TextSentenizerFactory()
        sentenizer = factory.create(TextFormat.SSML, "en")
        assert isinstance(sentenizer, SsmlSentenizer)

    def test_each_call_returns_fresh_usable_instance(self):
        factory = TextSentenizerFactory()
        first = factory.create(TextFormat.TEXT, "ru")
        second = factory.create(TextFormat.TEXT, "ru")
        assert first is not second
