from abc import ABC, abstractmethod


class TextNormalizer(ABC):
    """Represents the class to normalize raw text."""

    @abstractmethod
    async def normalize_text(self, text: str) -> str:
        """Return a normalized string from raw text."""
        ...


class PlainTextNormalizer(TextNormalizer):
    """Represents the class to normalize plain text."""

    async def normalize_text(self, text: str) -> str:
        if text is None:
            raise ValueError("Text is empty or whitespace")

        return text.strip()


class SsmlNormalizer(TextNormalizer):
    """Represents the class to normalize SSML."""

    async def normalize_text(self, text: str) -> str:
        if text is None:
            raise ValueError("Text is empty or whitespace")

        return text.strip()
