from loguru import logger
from openai import AsyncOpenAI

from src.tts.preprocessing.text_normalizer import TextNormalizer


class OpenAiTextNormalizer(TextNormalizer):
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        promt: str,
        temperature: float = 0.0,
        reasoning_effort: str = "none",
    ):
        self._client = client
        self._model = model
        self._promt = promt
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort

    async def normalize_text(self, text: str) -> str:
        if text is None:
            raise ValueError("text cannot be none or empty")

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._promt},
                    {"role": "user", "content": text},
                ],
                temperature=self._temperature,
                reasoning_effort=self._reasoning_effort,
                extra_body={"think": False},
            )

            clean_text = response.choices[0].message.content.strip()

            if not clean_text:
                logger.warning(
                    "{model_name} returned an empty response. Using original text",
                    model_name=self._model,
                )
            else:
                return clean_text
        except Exception:
            logger.exception(
                "{model_name} normalization failed with error. Returning original text",
                model_name=self._model,
            )

        return text
