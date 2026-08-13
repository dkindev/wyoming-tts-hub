from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

import numpy as np


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    model: str


@unique
class TextFormat(Enum):
    TEXT = "text"
    SSML = "ssml"


@unique
class NormalizationType(Enum):
    SIMPLE = "simple"
    OPENAI = "openai"


@unique
class BackendType(Enum):
    TORCH = "torch"


@unique
class EngineType(Enum):
    SILERO = "silero"
    QWEN = "qwen"
    OPENAI = "openai"


@dataclass(frozen=True)
class VoiceNormalization:
    voice_id: str
    text_format: TextFormat
    language: str
    type: NormalizationType
    enabled: bool
    prompt_id: str | None = None


@dataclass(frozen=True)
class Model:
    id: str
    engine_type: EngineType
    ssml_supported: bool = False
    language_auto_detected: bool = False
    languages: list[str] = field(default_factory=list)
    enabled: bool = True
    warmup: bool = False
    hash_prefix: str | None = None


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    speaker: str
    model_id: str
    ref_audio: str | None = None
    ref_text: str | None = None
    instruct: str | None = None


@dataclass(frozen=True)
class PredefinedData:
    models: list[Model]
    voices: list[Voice]
    prompts: list[Prompt] | None = None
    voice_normalizations: list[VoiceNormalization] | None = None


@dataclass(frozen=True)
class TTSConfig:
    device: str
    inference_timeout: float
    frame_duration: int
    sample_rate: int
    max_models: int
    cache_half_life: float
    max_concurrent_sentences_per_model: int
    max_sentence_chars: int
    models_dir: str
    models_yml_url: str
    models_yml_hash: str | None = None
    normalization_type: NormalizationType | None = None


@dataclass(frozen=True)
class NormalizationOptions:
    voice: Voice
    model: Model
    silero_model: Any


@dataclass(frozen=True)
class OpenAiNormalizationConfig:
    timeout: float
    max_concurrent_sentences_per_request: int
    default_model: str
    default_prompt: str


@dataclass(frozen=True)
class TTSResult:
    audio: np.ndarray
    sample_rate: int
    bytes_per_sample: int
    channels: int
