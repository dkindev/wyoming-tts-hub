import asyncio
import functools
import json
import os
from collections.abc import AsyncIterator
from typing import Any, cast

import numpy as np
import torch
from huggingface_hub import snapshot_download
from loguru import logger
from qwen_tts import Qwen3TTSModel

from src.tts.engine import TorchTtsEngine
from src.tts.models import ModelInfo, TextFormat, TtsResult, Voice
from src.tts.voice_prompt_cache import VoicePromptCache

CHECKPOINT_FAMILY_BASE = "base"
CHECKPOINT_FAMILY_CUSTOM_VOICE = "custom_voice"

CHECKPOINT_FAMILY_LABELS = {
    CHECKPOINT_FAMILY_BASE: "Base",
    CHECKPOINT_FAMILY_CUSTOM_VOICE: "CustomVoice",
    "voice_design": "VoiceDesign",
}
"""The checkpoint families Qwen3-TTS publishes, named for an error message."""

SUPPORTED_CHECKPOINT_FAMILIES = frozenset({CHECKPOINT_FAMILY_BASE, CHECKPOINT_FAMILY_CUSTOM_VOICE})
"""The checkpoint families this engine can synthesize with."""

INSTRUCTIONLESS_CHECKPOINT_SIZES = frozenset({"0b6"})
"""The CustomVoice sizes whose checkpoint ignores instructions entirely."""

AUTOMATIC_LANGUAGE = "Auto"
"""The checkpoint's own name for detecting the Language from the text."""

LANGUAGE_NAMES = {
    "auto": AUTOMATIC_LANGUAGE,
    "zh": "Chinese",
    "cmn": "Chinese",
    "en": "English",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "es": "Spanish",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "ru": "Russian",
}
"""Map a project Language code onto the English names the checkpoint speaks.

Qwen3-TTS validates Language against a small fixed set of lower-case English
names, plus its automatic mode. The project's Language is a code, so the engine
translates here rather than making every operator write the checkpoint's names.
"""


class UnsupportedCheckpointError(RuntimeError):
    """A checkpoint declares a family this engine cannot synthesize with."""


class QwenTtsEngine(TorchTtsEngine):
    """A Qwen3-TTS TTS Engine serving Base cloning and CustomVoice preset checkpoints."""

    def __init__(
        self,
        model_info: ModelInfo,
        device: str,
        models_dir: str,
        voice_prompt_capacity: int = 8,
    ):
        super().__init__(model_info, device)

        self._models_dir = models_dir
        self._loaded_model: Any | None = None
        self._checkpoint_family: str | None = None
        self._checkpoint_size: str | None = None
        self._instructionless_voices_warned: set[str] = set()
        self._voice_prompt_cache: VoicePromptCache = VoicePromptCache(
            capacity=voice_prompt_capacity
        )

    async def warmup(self) -> None:
        """Warm up the model, surfacing a rejected family without the wrapper.

        The base warmup wraps every failure in a generic message. A checkpoint of
        the wrong family is a configuration error the operator has to act on, so
        its message — which names the supported families — reaches them intact.
        """
        try:
            await super().warmup()
        except RuntimeError as error:
            if isinstance(error.__cause__, UnsupportedCheckpointError):
                raise error.__cause__ from None
            raise

    async def _warmup_on_device(self, device: torch.device) -> bool:
        loaded_model, checkpoint_family, checkpoint_size = await asyncio.to_thread(
            self._load_model_sync, self._model_info, device
        )

        self._loaded_model = loaded_model
        self._checkpoint_family = checkpoint_family
        self._checkpoint_size = checkpoint_size
        return True

    def _load_model_sync(
        self, model_info: ModelInfo, device: torch.device
    ) -> tuple[Any, str, str | None]:
        checkpoint_dir = self._checkpoint_dir(model_info)
        self._download_checkpoint(model_info, checkpoint_dir)
        checkpoint_config = self._read_checkpoint_config(model_info, checkpoint_dir)
        checkpoint_family = self._checkpoint_family_from_config(model_info, checkpoint_config)
        checkpoint_size = self._non_empty_string(checkpoint_config.get("tts_model_size"))

        logger.debug(
            "Loading Qwen3-TTS checkpoint '{model_id}' from '{path}' on '{device}'",
            model_id=model_info.id,
            path=checkpoint_dir,
            device=device.type,
        )

        loaded_model = Qwen3TTSModel.from_pretrained(
            checkpoint_dir,
            device_map=str(device),
        )

        loaded_size = self._non_empty_string(
            getattr(getattr(loaded_model, "model", None), "tts_model_size", None)
        )
        if loaded_size is not None:
            checkpoint_size = loaded_size

        return loaded_model, checkpoint_family, checkpoint_size

    @staticmethod
    def _non_empty_string(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _checkpoint_dir(self, model_info: ModelInfo) -> str:
        """The directory under the Models directory this checkpoint is kept in.

        The upstream id is a repository id, so its owner and name become nested
        directories. Path components that would escape the Models directory are
        dropped rather than followed.
        """
        parts = [part for part in model_info.id.split("/") if part not in ("", ".", "..")]
        return os.path.join(self._models_dir, "qwen", *parts)

    @staticmethod
    def _download_checkpoint(model_info: ModelInfo, checkpoint_dir: str) -> None:
        os.makedirs(checkpoint_dir, exist_ok=True)

        try:
            snapshot_download(
                repo_id=model_info.id,
                revision=model_info.revision,
                local_dir=checkpoint_dir,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to download Qwen3-TTS checkpoint '{model_info.id}'") from e

    @staticmethod
    def _read_checkpoint_config(model_info: ModelInfo, checkpoint_dir: str) -> dict[str, Any]:
        """Read the checkpoint's own declaration, before loading it."""
        config_path = os.path.join(checkpoint_dir, "config.json")

        try:
            with open(config_path, encoding="utf-8") as config_file:
                config = json.load(config_file)
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"Failed to read the Qwen3-TTS checkpoint configuration for "
                f"'{model_info.id}' at '{config_path}'"
            ) from e

        if not isinstance(config, dict):
            raise RuntimeError(
                f"The Qwen3-TTS checkpoint configuration for '{model_info.id}' at "
                f"'{config_path}' must be a JSON object"
            )

        return config

    @staticmethod
    def _checkpoint_family_from_config(
        model_info: ModelInfo, checkpoint_config: dict[str, Any]
    ) -> str:
        family = checkpoint_config.get("tts_model_type")
        if isinstance(family, str) and family in SUPPORTED_CHECKPOINT_FAMILIES:
            return family

        declared = CHECKPOINT_FAMILY_LABELS.get(family, repr(family))
        supported = ", ".join(
            CHECKPOINT_FAMILY_LABELS[name] for name in sorted(SUPPORTED_CHECKPOINT_FAMILIES)
        )

        raise UnsupportedCheckpointError(
            f"Qwen3-TTS checkpoint '{model_info.id}' declares the '{declared}' family, "
            f"but only {supported} checkpoints are supported"
        )

    async def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        if self._checkpoint_family == CHECKPOINT_FAMILY_CUSTOM_VOICE:
            wavs, sample_rate = await self._synthesize_custom_voice(text, voice, language)
        elif self._checkpoint_family == CHECKPOINT_FAMILY_BASE:
            wavs, sample_rate = await self._synthesize_voice_clone(text, voice, language)
        else:
            raise UnsupportedCheckpointError(
                f"Qwen3-TTS checkpoint '{self._model_info.id}' does not support synthesis"
            )

        for wav in wavs:
            yield TtsResult(
                audio=self._to_pcm16(wav),
                sample_rate=sample_rate,
                bytes_per_sample=2,
                channels=1,
            )

    async def _synthesize_voice_clone(
        self, text: str, voice: Voice, language: str | None
    ) -> tuple[list[np.ndarray], int]:
        if not voice.ref_audio:
            raise ValueError(
                f"Voice '{voice.id}' has no Reference Audio, but model "
                f"'{self._model_info.id}' is a Base checkpoint that clones from one"
            )

        checkpoint_language = self._checkpoint_language(language, voice)
        return await asyncio.to_thread(
            self._synthesize_voice_clone_sync,
            text,
            voice,
            checkpoint_language,
        )

    def _synthesize_voice_clone_sync(
        self, text: str, voice: Voice, language: str
    ) -> tuple[list[np.ndarray], int]:
        loaded_model = self._loaded_model
        assert loaded_model is not None

        build_voice_prompt = functools.partial(self._build_voice_prompt, loaded_model)
        voice_prompt = self._voice_prompt_cache.get_or_create(voice, build_voice_prompt)

        return cast(
            tuple[list[np.ndarray], int],
            loaded_model.generate_voice_clone(
                text=text,
                language=language,
                voice_clone_prompt=voice_prompt,
            ),
        )

    async def _synthesize_custom_voice(
        self, text: str, voice: Voice, language: str | None
    ) -> tuple[list[np.ndarray], int]:
        if not voice.speaker:
            raise ValueError(
                f"Voice '{voice.id}' has no Speaker, but model "
                f"'{self._model_info.id}' is a CustomVoice checkpoint that needs one"
            )

        self._validate_custom_voice_speaker(voice)
        checkpoint_language = self._custom_voice_language(language, voice)
        instruction = self._custom_voice_instruction(voice)

        return await asyncio.to_thread(
            self._synthesize_custom_voice_sync,
            text,
            voice,
            checkpoint_language,
            instruction,
        )

    def _synthesize_custom_voice_sync(
        self, text: str, voice: Voice, language: str, instruction: str | None
    ) -> tuple[list[np.ndarray], int]:
        loaded_model = self._loaded_model
        assert loaded_model is not None

        return cast(
            tuple[list[np.ndarray], int],
            loaded_model.generate_custom_voice(
                text=text,
                language=language,
                speaker=voice.speaker.strip(),
                instruct=instruction,
            ),
        )

    def _validate_custom_voice_speaker(self, voice: Voice) -> None:
        supported = self._supported_values("get_supported_speakers")
        if supported is None or voice.speaker.strip().lower() in supported:
            return

        raise ValueError(
            f"Unsupported Speaker '{voice.speaker}' for Voice '{voice.id}': Qwen3-TTS "
            f"checkpoint '{self._model_info.id}' supports: "
            f"{', '.join(sorted(supported))}"
        )

    def _custom_voice_language(self, language: str | None, voice: Voice) -> str:
        """Translate a Language code, refusing one the checkpoint cannot speak."""
        if language is None:
            return AUTOMATIC_LANGUAGE

        name = self._language_name(language)
        if name is None:
            raise ValueError(
                f"Unsupported Language '{language}' for Voice '{voice.id}': Qwen3-TTS "
                f"checkpoint '{self._model_info.id}' does not recognise that code"
            )

        supported = self._supported_values("get_supported_languages")
        if supported is not None and name.lower() not in supported:
            raise ValueError(
                f"Unsupported Language '{language}' ({name}) for Voice '{voice.id}': "
                f"Qwen3-TTS checkpoint '{self._model_info.id}' supports: "
                f"{', '.join(sorted(supported))}"
            )

        return name

    def _custom_voice_instruction(self, voice: Voice) -> str | None:
        instruction = (voice.instruct or "").strip() or None
        if instruction is None:
            return None

        if self._checkpoint_size in INSTRUCTIONLESS_CHECKPOINT_SIZES:
            if voice.id not in self._instructionless_voices_warned:
                self._instructionless_voices_warned.add(voice.id)
                logger.warning(
                    "Voice '{voice_id}' configures an instruction, but Qwen3-TTS checkpoint "
                    "'{model_id}' is the '{size}' size, which ignores instructions; the "
                    "instruction will not be applied",
                    voice_id=voice.id,
                    model_id=self._model_info.id,
                    size=self._checkpoint_size,
                )
            return None

        return instruction

    def _supported_values(self, method_name: str) -> frozenset[str] | None:
        loaded_model = self._loaded_model
        if loaded_model is None:
            return None

        getter = getattr(loaded_model, method_name, None)
        if not callable(getter):
            return None

        values = getter()
        if values is None:
            return None

        return frozenset(str(value).lower() for value in values)

    @staticmethod
    def _build_voice_prompt(loaded_model: Any, voice: Voice):
        ref_text = (voice.ref_text or "").strip() or None
        x_vector_only_mode = ref_text is None

        if x_vector_only_mode:
            logger.warning(
                "Voice '{voice_id}' has no reference text, so it is cloned from the "
                "speaker embedding alone and quality is reduced",
                voice_id=voice.id,
            )

        return loaded_model.create_voice_clone_prompt(
            ref_audio=voice.ref_audio,
            ref_text=ref_text,
            x_vector_only_mode=x_vector_only_mode,
        )

    @staticmethod
    def _language_name(language: str) -> str | None:
        """Translate a project Language code into the checkpoint's language name."""
        code = language.strip().lower()
        return LANGUAGE_NAMES.get(code) or LANGUAGE_NAMES.get(code.split("-", 1)[0])

    @classmethod
    def _checkpoint_language(cls, language: str | None, voice: Voice) -> str:
        """Translate a Base Voice's Language, falling back to automatic detection."""
        if language is None:
            return AUTOMATIC_LANGUAGE

        name = cls._language_name(language)
        if name is None:
            logger.warning(
                "Language '{language}' is not recognised for Voice '{voice_id}', so "
                "the Qwen3-TTS checkpoint will detect the language automatically",
                language=language,
                voice_id=voice.id,
            )
            return AUTOMATIC_LANGUAGE

        return name

    @staticmethod
    def _to_pcm16(audio: np.ndarray) -> np.ndarray:
        """Convert the checkpoint's float audio to mono 16-bit PCM."""
        samples = np.asarray(audio, dtype=np.float32)

        if samples.ndim > 1:
            samples = samples[0] if samples.shape[0] == 1 else samples.mean(axis=-1)

        samples = np.clip(samples, -1.0, 1.0)
        return (samples * 32767.0).astype(np.int16)

    def _release_resources(self) -> None:
        self._loaded_model = None
        self._checkpoint_family = None
        self._checkpoint_size = None
        self._instructionless_voices_warned.clear()
        self._voice_prompt_cache.clear()
        super()._release_resources()
