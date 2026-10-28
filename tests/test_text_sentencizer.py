from src.tts.preprocessing import PlainTextSentencizer, SsmlSentencizer


class TestSsmlSentencizer:
    """Tests for SsmlSentencizer.text_to_sentences behavior."""

    def test_valid_ssml_preserves_structure(self):
        text = "<speak>hello world</speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 100))
        assert sentences == ["<speak>hello world</speak>"]

    def test_invalid_ssml_falls_back_to_text_split(self):
        text = "<speak><p>hello</speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 100))
        assert sentences == ["<speak>hello</speak>"]

    def test_empty_ssml_return_empty_sentence(self):
        text = "<speak></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert len(sentences) == 0

    def test_empty_ssml_tag_return_empty_sentence(self):
        text = "<speak><p></p></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert len(sentences) == 0

    def test_ssml_splits_long_text_and_reopens_tags(self):
        text = "<speak><p>hello world foo bar baz</p></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert sentences == [
            "<speak><p>hello</p></speak>",
            "<speak><p>world foo</p></speak>",
            "<speak><p>bar baz</p></speak>",
        ]

    def test_nested_tag_not_swallowed_by_skip_closing(self):
        text = "<speak><p>LONGWORDSHERE <s>inner</s> tail</p></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert sentences == [
            "<speak><p>LONGWORDSH</p></speak>",
            "<speak><p>ERE</p></speak>",
            "<speak><p><s>inner</s> tail</p></speak>",
        ]

    def test_double_nesting_with_overflow_at_outer_level(self):
        text = "<speak><p><s>LONGWORDSHERE inner</s>tail</p></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert sentences == [
            "<speak><p><s>LONGWORDSH</s></p></speak>",
            "<speak><p><s>ERE inner</s></p></speak>",
            "<speak><p>tail</p></speak>",
        ]

    def test_sibling_tags_after_long_text_overflow(self):
        text = "<speak><p>LONGWORDSHERE <s>inner</s><b>bold</b></p></speak>"
        sentences = list(SsmlSentencizer(PlainTextSentencizer()).text_to_sentences(text, 10))
        assert sentences == [
            "<speak><p>LONGWORDSH</p></speak>",
            "<speak><p>ERE</p></speak>",
            "<speak><p><s>inner</s><b>bold</b></p></speak>",
        ]


class TestSimpleTextSentencizer:
    """Tests for PlainTextSentencizer.text_to_sentences behavior."""

    def test_short_text_returns_single_sentence(self):
        text = "hello world"
        sentences = list(PlainTextSentencizer().text_to_sentences(text, 100))
        assert sentences == ["hello world"]

    def test_long_text_splits_on_sentence_boundary(self):
        text = "first sentence here. second one longer. third one"
        sentences = list(PlainTextSentencizer().text_to_sentences(text, 20))
        assert sentences == ["first sentence here.", "second one longer.", "third one"]

    def test_long_sentence_splits_on_minor_punctuation(self):
        text = "this is a very long sentence, broken by a comma, and then ended"
        sentences = list(PlainTextSentencizer().text_to_sentences(text, 20))
        assert sentences == [
            "this is a very long",
            "sentence,",
            "broken by a comma,",
            "and then ended",
        ]

    def test_splits_by_words_when_no_punctuation(self):
        text = "hello world foo bar"
        sentences = list(PlainTextSentencizer().text_to_sentences(text, 10))
        assert sentences == ["hello", "world foo", "bar"]

    def test_hard_splits_giant_word(self):
        text = "superlongword"
        sentences = list(PlainTextSentencizer().text_to_sentences(text, 5))
        assert sentences == ["super", "longw", "ord"]
