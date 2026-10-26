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
    QWEN3 = "qwen3"
    OPENAI = "openai"


ENGINE_REPO_URLS: dict[EngineType, str] = {
    EngineType.SILERO: "https://github.com/snakers4/silero-models",
    EngineType.QWEN3: "https://github.com/QwenLM/Qwen3-TTS",
    EngineType.OPENAI: "https://openai.com",
}
"""Where each TTS Engine family comes from, keyed by the family itself.

Declared beside the families rather than where they are advertised, so a client reading
a Voice's attribution is told which TTS Engine produced it, and adding an engine does
not mean editing the protocol handler. The family values stay the bare names a data file
writes and the Engine Factory keys its builders on, so carrying a URL here cannot change
what `engine_type: silero` parses as.

The OpenAI-compatible family points at the vendor's site: it speaks an API rather than
shipping a project, so there is no upstream repository to point a client at.
"""


@dataclass(frozen=True)
class VoiceNormalization:
    voice_id: str
    text_format: TextFormat
    language: str
    type: NormalizationType
    enabled: bool
    prompt_id: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    """The configuration of one named model a TTS Engine can be built for."""

    id: str
    engine_type: EngineType
    ssml_supported: bool = False
    language_auto_detected: bool = False
    languages: list[str] = field(default_factory=list)
    enabled: bool = True
    warmup: bool = False
    hash_prefix: str | None = None
    revision: str | None = None


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
    models: list[ModelInfo]
    voices: list[Voice]
    prompts: list[Prompt] | None = None
    voice_normalizations: list[VoiceNormalization] | None = None


@dataclass(frozen=True)
class TtsResult:
    audio: np.ndarray
    sample_rate: int
    bytes_per_sample: int
    channels: int

    def __post_init__(self) -> None:
        """Refuse audio with no sample axis, and keep audio that is contiguous.

        A TTS Engine synthesizes into a buffer whose layout it does not choose, so the
        contiguity guarantee is made here rather than left to each Engine to remember.
        Audio that is already contiguous is kept as it is, so no copy is paid for it.

        Audio with no sample axis is refused first, because the TTS Engine Hub frames
        audio by slicing a leading axis: a Chunk without one fails there as an index
        error, long after the TTS Engine that produced it has moved on, and it is the
        Engine that can fix it.

        Empty audio is not refused. A Chunk carrying no samples is silence, and an empty
        payload is skipped on the wire.
        """
        if self.audio.ndim == 0:
            raise ValueError(
                f"Audio must have a sample axis to frame, but got shape {self.audio.shape}"
            )

        if not self.audio.flags["C_CONTIGUOUS"]:
            object.__setattr__(self, "audio", np.ascontiguousarray(self.audio))
