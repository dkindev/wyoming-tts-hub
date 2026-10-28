from collections.abc import Iterator

from razdel import sentenize

from src.tts.preprocessing.text_sentencizer import PlainTextSentencizer


class RuPlainTextSentencizer(PlainTextSentencizer):
    """Represents a class for generating sentences from Russian text."""

    def text_to_sentences(self, text: str, max_sentence_chars: int) -> Iterator[str]:
        """Generate a sentences from an plain text."""
        if not text:
            return

        if max_sentence_chars <= 0:
            raise ValueError("max_sentence_chars cannot be negative or zero")

        if len(text) <= max_sentence_chars:
            yield text
            return

        pre_sentences = RuPlainTextSentencizer.sentencize_by_nlp(
            sentence=text, max_sentence_chars=max_sentence_chars
        )
        yield from self._assembly_small_sentences(
            sentences=pre_sentences, max_sentence_chars=max_sentence_chars
        )

    @staticmethod
    def sentencize_by_nlp(sentence: str, max_sentence_chars: int) -> Iterator[str]:
        for sentence_obj in sentenize(sentence):
            sentence_text = sentence_obj.text.strip()
            if not sentence_text:
                continue

            if len(sentence_text) <= max_sentence_chars:
                yield sentence_text
            else:
                yield from PlainTextSentencizer.sentencize_by_minor_characters(
                    sentence=sentence_text, max_sentence_chars=max_sentence_chars
                )
