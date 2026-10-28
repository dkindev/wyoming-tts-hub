import re
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Iterator

from loguru import logger

MINOR_CHARACTERS_RE = re.compile(r"(?<=[,:\-—;])\s+")
PUNCTUATIONS_RE = re.compile(r"(?<=[.!?\n])\s+")
WORD_RE = re.compile(r"\S+")


class TextSentencizer(ABC):
    """Represents a class for generating sentences from source text."""

    @abstractmethod
    def text_to_sentences(self, text: str, max_sentence_chars: int) -> Iterator[str]:
        ...


class PlainTextSentencizer(TextSentencizer):
    """Represents a class for generating sentences from plain text."""

    def text_to_sentences(self, text: str, max_sentence_chars: int) -> Iterator[str]:
        """Generate a sentences from an plain text."""
        if not text:
            return

        if max_sentence_chars <= 0:
            raise ValueError("max_sentence_chars cannot be negative or zero")

        if len(text) <= max_sentence_chars:
            yield text
            return

        pre_sentences = PlainTextSentencizer.sentencize_by_punctuations(text, max_sentence_chars)
        yield from self._assembly_small_sentences(
            sentences=pre_sentences, max_sentence_chars=max_sentence_chars
        )

    def _assembly_small_sentences(
        self, sentences: Iterator[str], max_sentence_chars: int
    ) -> Iterator[str]:
        """Assembly of small pieces into optimal sentences up to max_sentence_chars"""
        current_sentence = []
        current_length = 0
        item_length = 0

        for item in sentences:
            item = item.strip()
            if not item:
                continue

            item_length = len(item)

            if current_length + item_length > max_sentence_chars:
                if current_sentence:
                    yield " ".join(current_sentence)
                current_sentence = [item]
                current_length = item_length
            else:
                current_sentence.append(item)
                current_length += item_length + 1

        if current_sentence:
            yield " ".join(current_sentence)

    @staticmethod
    def sentencize_by_punctuations(sentence: str, max_sentence_chars: int) -> Iterator[str]:
        last_idx = 0

        for match in PUNCTUATIONS_RE.finditer(sentence):
            segment = sentence[last_idx : match.start()].strip()
            last_idx = match.end()

            if segment:
                if len(segment) <= max_sentence_chars:
                    yield segment
                else:
                    yield from PlainTextSentencizer.sentencize_by_minor_characters(
                        segment, max_sentence_chars
                    )

        last_segment = sentence[last_idx:].strip()
        if last_segment:
            if len(last_segment) <= max_sentence_chars:
                yield last_segment
            else:
                yield from PlainTextSentencizer.sentencize_by_minor_characters(
                    last_segment, max_sentence_chars
                )

    @staticmethod
    def sentencize_by_minor_characters(sentence: str, max_sentence_chars: int) -> Iterator[str]:
        last_idx = 0

        for match in MINOR_CHARACTERS_RE.finditer(sentence):
            segment = sentence[last_idx : match.start()].strip()
            last_idx = match.end()

            if segment:
                if len(segment) <= max_sentence_chars:
                    yield segment
                else:
                    yield from PlainTextSentencizer.sentencize_by_words(segment, max_sentence_chars)

        last_segment = sentence[last_idx:].strip()
        if last_segment:
            if len(last_segment) <= max_sentence_chars:
                yield last_segment
            else:
                yield from PlainTextSentencizer.sentencize_by_words(
                    last_segment, max_sentence_chars
                )

    @staticmethod
    def sentencize_by_words(sentence: str, max_sentence_chars: int) -> Iterator[str]:
        sentence_start = -1
        sentence_end = -1

        for match in WORD_RE.finditer(sentence):
            w_start, w_end = match.start(), match.end()
            w_len = w_end - w_start

            # If ONE word is longer than the limit (link, token, long hash)
            if w_len > max_sentence_chars:
                if sentence_start != -1:
                    yield sentence[sentence_start:sentence_end]
                    sentence_start, sentence_end = -1, -1

                # Let's cut this giant word character by character right here.
                word = match.group()
                for i in range(0, w_len, max_sentence_chars):
                    yield word[i : i + max_sentence_chars]
                continue

            if sentence_start == -1:
                sentence_start, sentence_end = w_start, w_end
                continue

            potential_len = w_end - sentence_start

            if potential_len > max_sentence_chars:
                yield sentence[sentence_start:sentence_end]
                sentence_start, sentence_end = w_start, w_end
            else:
                sentence_end = w_end

        if sentence_start != -1:
            yield sentence[sentence_start:sentence_end]


TAGS_RE = re.compile(r"<[^>]+>")
TAGS_SPLIT_RE = re.compile(r"(<[^>]+>|[^<]+)")
EMPTY_XML_NODES_RE = re.compile(r"<(\w+)[^>]*>\s*</\1>")
OPENING_TAG_RE = re.compile(r"<([a-zA-Z0-9]+)")
TAG_TRAILING_WHITESPACE_RE = re.compile(r"(\s+)(?=<|</)")


class SsmlSentencizer(TextSentencizer):
    """Represents a class for generating sentences from SSML."""

    def __init__(self, text_sentencizer_in_tags: TextSentencizer):
        self._text_sentencizer_in_tags = text_sentencizer_in_tags

    def text_to_sentences(self, text: str, max_sentence_chars: int) -> Iterator[str]:
        """Generate a sentences from an SSML."""
        if not text:
            return

        if max_sentence_chars <= 0:
            raise ValueError("max_sentence_chars cannot be negative or zero")

        ssml_text = text.strip()
        if not ssml_text.startswith("<speak>"):
            ssml_text = f"<speak>{ssml_text}</speak>"

        try:
            ET.fromstring(ssml_text)
        except ET.ParseError as e:
            logger.warning(
                "SSML isn't valid. Falling back to text splitting. Exception: {exc}", exc=e
            )

            clean_text = TAGS_RE.sub("", ssml_text)
            for sentence in self._text_sentencizer_in_tags.text_to_sentences(
                clean_text, max_sentence_chars
            ):
                yield f"<speak>{sentence}</speak>"

            return

        if len(ssml_text) <= max_sentence_chars:
            yield ssml_text
            return

        yield from self._sentencize_ssml_into_sentences(ssml_text, max_sentence_chars)

    def _sentencize_ssml_into_sentences(  # noqa: C901
        self, ssml_text: str, max_sentence_chars: int
    ) -> Iterator[str]:
        current_sentence = []
        text_len = 0
        opened_tags = []

        if ssml_text.startswith("<speak>") and ssml_text.endswith("</speak>"):
            ssml_content = ssml_text[7:-8]
        else:
            ssml_content = ssml_text

        for match in TAGS_SPLIT_RE.finditer(ssml_content):
            token = match.group(1)
            if not token:
                continue

            if token.startswith("<"):
                current_sentence.append(token)

                if token.endswith("/>"):
                    continue

                if not token.startswith("</"):
                    tag_match = OPENING_TAG_RE.match(token)
                    if tag_match:
                        opened_tags.append(tag_match.group(1))
                else:
                    tag_match = OPENING_TAG_RE.match(token.replace("/", ""))
                    if tag_match and opened_tags and opened_tags[-1] == tag_match.group(1):
                        opened_tags.pop()
            else:
                if text_len + len(token) <= max_sentence_chars:
                    current_sentence.append(token)
                    text_len += len(token)
                else:
                    prefix_tokens = [f"<{tag}>" for tag in opened_tags]

                    if text_len > 0:
                        yield self._build_valid_sentence(current_sentence, opened_tags)
                        current_sentence = []
                        text_len = 0

                    if len(token) <= max_sentence_chars:
                        current_sentence = prefix_tokens + [token]
                        text_len = len(token)
                    else:
                        for sub_sentence in self._text_sentencizer_in_tags.text_to_sentences(
                            token, max_sentence_chars
                        ):
                            yield self._build_valid_sentence(
                                prefix_tokens + [sub_sentence], opened_tags
                            )

                        opened_tags.clear()
                        current_sentence = prefix_tokens

        if current_sentence and text_len > 0:
            yield self._build_valid_sentence(current_sentence, opened_tags)

    @staticmethod
    def _build_valid_sentence(tokens: list[str], opened_tags: list[str]) -> str:
        """Assembles, cleans up, and wraps a sentence in valid SSML structure."""
        raw_sentence = "".join(tokens)

        if opened_tags:
            closing_str = "".join(f"</{tag}>" for tag in reversed(opened_tags))
            raw_sentence += closing_str

        cleaned = TAG_TRAILING_WHITESPACE_RE.sub("", raw_sentence)
        cleaned = EMPTY_XML_NODES_RE.sub("", cleaned)
        cleaned = cleaned.strip()

        return f"<speak>{cleaned}</speak>"
