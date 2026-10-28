import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

import torch
from loguru import logger

from src.tts.models import (
    ModelInfo,
    TextFormat,
    TtsResult,
    Voice,
)


class TtsEngine(ABC):
    def __init__(self, model_info: ModelInfo):
        self._model_info = model_info
        self._loaded = False
        self._lock = asyncio.Lock()

    @property
    def model_info(self) -> ModelInfo:
        """The ModelInfo this engine was built for."""
        return self._model_info

    async def synthesize_pcm(
        self, text: str, voice: Voice, text_format: TextFormat, language: str | None = None
    ) -> AsyncIterator[TtsResult]:
        text = text.strip()
        if not text:
            raise ValueError("Text is empty or whitespace")

        if not voice:
            raise ValueError("Voice cannot be none")

        if voice.model_id != self._model_info.id:
            raise ValueError(f"Unsupported voice: {voice.id}")

        if not self._loaded:
            await self.warmup(voices=[voice])

        async for item in self._synthesize_pcm(text, voice, text_format, language):
            yield item

    async def warmup(self, voices: list[Voice] | None = None) -> None:
        if self._loaded:
            return

        async with self._lock:
            if self._loaded:
                return

            logger.debug(
                "Warming up model '{model_id}'",
                model_id=self._model_info.id,
            )

            try:
                self._loaded = await self._warmup(voices)
                logger.debug("Model '{model}' has been warmed up.", model=self._model_info.id)
            except Exception as e:
                raise RuntimeError(f"Failed to warm up the model '{self._model_info.id}'") from e

    async def close(self) -> None:
        async with self._lock:
            self._release_resources()

    def _release_resources(self) -> None:
        return

    @abstractmethod
    async def _warmup(self, voices: list[Voice] | None = None) -> bool:
        ...

    @abstractmethod
    def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        ...


class TorchTtsEngine(TtsEngine):
    @property
    def device(self) -> torch.device | None:
        return self._device

    def __init__(self, model_info: ModelInfo, device: str):
        super().__init__(model_info)

        self._target_device = device
        self._device: torch.device | None = None

    async def _warmup(self, voices: list[Voice] | None = None) -> bool:
        device = self._resolve_device()

        logger.debug(
            "Warming up model '{model_id}' on '{device}'",
            model_id=self._model_info.id,
            device=device.type,
        )

        result = await self._warmup_on_device(device, voices)

        if result:
            self._device = device

        return result

    def _resolve_device(self) -> torch.device:
        try:
            device = torch.device(self._target_device)
        except RuntimeError:
            logger.warning(
                "Invalid device string '{device}'. Falling back to cpu.", device=self._target_device
            )
            return torch.device("cpu")

        if device.type == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available. Falling back to cpu.")
            return torch.device("cpu")
        elif device.type == "mps" and (
            not hasattr(torch.backends, "mps") or not torch.backends.mps.is_available()
        ):
            logger.warning("MPS requested but not available/supported. Falling back to cpu.")
            return torch.device("cpu")
        elif device.type == "xpu" and (not hasattr(torch, "xpu") or not torch.xpu.is_available()):
            logger.warning("XPU requested but not available/supported. Falling back to cpu.")
            return torch.device("cpu")

        return device

    @abstractmethod
    async def _warmup_on_device(
        self, device: torch.device, voices: list[Voice] | None = None
    ) -> bool:
        ...
