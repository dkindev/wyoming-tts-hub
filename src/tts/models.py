from dataclasses import dataclass, field
from enum import Enum, unique

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
class TtsResult:
    audio: np.ndarray
    sample_rate: int
    bytes_per_sample: int
    channels: int
