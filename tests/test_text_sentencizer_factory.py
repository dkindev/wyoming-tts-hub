from src.tts.models import TextFormat
from src.tts.preprocessing import (
    PlainTextSentencizer,
    RuPlainTextSentencizer,
    SsmlSentencizer,
    TextSentencizerFactory,
)


class TestTextSentencizerFactory:
    """Tests for TextSentencizerFactory.create behavior."""

    def test_default_text_resolves_plain_text_sentencizer(self):
        factory = TextSentencizerFactory()
        sentencizer = factory.create(TextFormat.TEXT)
        assert isinstance(sentencizer, PlainTextSentencizer)

    def test_default_text_with_none_language_resolves_plain_text_sentencizer(self):
        factory = TextSentencizerFactory()
        sentencizer = factory.create(TextFormat.TEXT, None)
        assert isinstance(sentencizer, PlainTextSentencizer)

    def test_ru_text_resolves_ru_plain_text_sentencizer(self):
        factory = TextSentencizerFactory()
        sentencizer = factory.create(TextFormat.TEXT, "ru")
        assert isinstance(sentencizer, RuPlainTextSentencizer)

    def test_unknown_language_falls_back_to_default_text(self):
        factory = TextSentencizerFactory()
        sentencizer = factory.create(TextFormat.TEXT, "en")
        assert isinstance(sentencizer, PlainTextSentencizer)

    def test_unknown_language_falls_back_to_default_ssml(self):
        factory = TextSentencizerFactory()
        sentencizer = factory.create(TextFormat.SSML, "en")
        assert isinstance(sentencizer, SsmlSentencizer)

    def test_each_call_returns_fresh_usable_instance(self):
        factory = TextSentencizerFactory()
        first = factory.create(TextFormat.TEXT, "ru")
        second = factory.create(TextFormat.TEXT, "ru")
        assert first is not second
