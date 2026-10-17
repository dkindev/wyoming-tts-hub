from src.tts.preprocessing import RuPlainTextSentencizer


class TestRuSimpleTextSentencizer:
    """Tests for RuPlainTextSentencizer.text_to_sentences behavior."""

    def test_short_text_returns_single_sentence(self):
        text = "привет мир"
        sentences = list(RuPlainTextSentencizer().text_to_sentences(text, 100))
        assert sentences == ["привет мир"]

    def test_splits_on_sentence_boundary(self):
        text = "Иди сюда. Подожди минутку. Хорошо"
        sentences = list(RuPlainTextSentencizer().text_to_sentences(text, 20))
        assert sentences == ["Иди сюда.", "Подожди минутку.", "Хорошо"]

    def test_razdel_handles_abbreviations(self):
        text = "Он т.е. пришёл. Да"
        sentences = list(RuPlainTextSentencizer().text_to_sentences(text, 17))
        assert sentences == ["Он т.е. пришёл.", "Да"]

    def test_long_sentence_splits_on_comma(self):
        text = "это очень длинное предложение, разбитое запятой, и законченное"
        sentences = list(RuPlainTextSentencizer().text_to_sentences(text, 20))
        assert sentences == [
            "это очень длинное",
            "предложение,",
            "разбитое запятой,",
            "и законченное",
        ]

    def test_hard_splits_giant_word(self):
        text = "супердлинноеслово"
        sentences = list(RuPlainTextSentencizer().text_to_sentences(text, 5))
        assert sentences == ["супер", "длинн", "оесло", "во"]
