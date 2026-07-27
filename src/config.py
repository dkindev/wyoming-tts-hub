import argparse
import os
import re
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

from src import __metadata__
from src.tts.models import NormalizationType


class TorchSettings(BaseModel):
    device: str = Field(
        default="cpu",
        description="Device to run TTS model on: 'cpu', 'cuda', etc. Falls back to 'cpu' at runtime if unavailable.",
    )
    """Device to run TTS model on: 'cpu', 'cuda', etc. Falls back to 'cpu' at runtime if unavailable."""

    num_threads: int = Field(
        default=4,
        ge=1,
        description="Number of PyTorch intra-op threads (torch.set_num_threads).",
    )
    """Number of PyTorch intra-op threads (torch.set_num_threads)."""

    num_interop_threads: int = Field(
        default=1,
        ge=1,
        description="Number of PyTorch inter-op threads (torch.set_num_interop_threads).",
    )
    """Number of PyTorch inter-op threads (torch.set_num_interop_threads)."""

    flush_denormal: bool = Field(
        default=True,
        description="Flush denormal floats for performance (torch.set_flush_denormal).",
    )
    """Flush denormal floats for performance (torch.set_flush_denormal)."""


class NormalizationPrompt(BaseModel):
    text: str = Field(default="", description="System prompt for normalization.")
    """System prompt for normalization."""

    model: str = Field(
        default="",
        description="System LLM model name for normalization.",
    )
    """System LLM model name for normalization."""


class BaseNormalizationSettings(BaseModel):
    type: NormalizationType = Field(
        default=NormalizationType.SIMPLE, description="Normalizer type (simple, llm)."
    )
    """Normalizer type (simple, llm)."""

    prompts: dict[str, NormalizationPrompt] | None = Field(
        default_factory=dict, description="A dictionary of prompts indexed by locale."
    )
    """A dictionary of prompts indexed by locale."""


class TextNormalizationSettings(BaseNormalizationSettings):
    enabled: bool = Field(
        default=True,
        description="Enable plain text normalization.",
    )
    """Enable plain text normalization."""


class SsmlNormalizationSettings(BaseNormalizationSettings):
    enabled: bool = Field(
        default=False,
        description="Enable SSML markup normalization.",
    )
    """Enable SSML markup normalization."""


class NormalizationSettings(BaseModel):
    timeout: float = Field(
        default=5,
        ge=1,
        description="Timeout for input text normalization in seconds.",
    )
    """Timeout for input text normalization in seconds."""

    max_concurrent_sentences_per_request: int = Field(
        default=2,
        ge=1,
        description="Maximum concurrent sentences per request for normalization.",
    )
    """Maximum concurrent sentences per request for normalization."""

    text: TextNormalizationSettings = Field(default_factory=TextNormalizationSettings)
    ssml: SsmlNormalizationSettings = Field(default_factory=SsmlNormalizationSettings)


class OpenAiSettings(BaseModel):
    base_url: str = Field(
        default="",
        description="Base URL for OpenAI-compatible API.",
    )
    """Base URL for OpenAI-compatible API."""

    api_key: str = Field(
        default="",
        description="API key for OpenAI-compatible API.",
    )
    """API key for OpenAI-compatible API."""

    @model_validator(mode="after")
    def fallback_to_standard_openai_envs(self) -> "OpenAiSettings":
        # If after all sources (YAML, CLI, TTS_*) the fields remains empty
        # use standart OpenAI envs
        if not self.api_key:
            standard_key = os.environ.get("OPENAI_API_KEY")
            if standard_key:
                self.api_key = standard_key

        if not self.base_url:
            standard_url = os.environ.get("OPENAI_BASE_URL")
            if standard_url:
                self.base_url = standard_url

        return self


class SileroSettings(BaseModel):
    sample_rate: Literal[8000, 16000, 24000, 48000] = Field(
        default=48000,
        description="Audio sample rate in Hz (8000, 16000, 24000, 48000).",
    )
    """Audio sample rate in Hz (8000, 16000, 24000, 48000)."""

    @field_validator("sample_rate", mode="before")
    @classmethod
    def coerce_sample_rate(cls, v: object) -> object:
        if isinstance(v, str):
            return int(v)
        return v

    models_dir: str = Field(
        default="models/silero",
        description="Directory for downloaded Silero .pt model files.",
    )
    """Directory for downloaded Silero .pt model files."""

    models_yml_url: HttpUrl = Field(
        default="https://raw.githubusercontent.com/snakers4/silero-models/refs/heads/master/models.yml",
        description="URL to the Silero models.yml registry file.",
    )
    """URL to the Silero models.yml registry file."""

    models_yml_hash: str = Field(
        default="",
        description="SHA-256 hash of the Silero models.yml file for integrity verification. Set empty to skip validation.",
    )
    """SHA-256 hash of the Silero models.yml file for integrity verification. Set empty to skip validation."""

    @field_validator("models_yml_hash")
    @classmethod
    def models_yml_hash_must_be_valid(cls, v: str) -> str:
        if v and not v.strip():
            return ""
        if v:
            import re

            if not re.fullmatch(r"[a-f0-9]{64}", v.lower()):
                raise ValueError(
                    "TTS_MODELS_YML_HASH must be a 64-character hex string or empty to skip validation"
                )
        return v


class Settings(BaseSettings):
    app_name: str = Field(
        default="Wyoming TTS Hub",
        description="Application name. Used as a Wyoming service name.",
    )
    """Application name. Used as a Wyoming service name."""

    env_type: Literal["development", "production"] = Field(
        default="development",
        description="Application environment type. Controls error detail level and other environment-specific behavior.",
    )
    """Application environment type. Controls error detail level and other environment-specific behavior."""

    uri: str = Field(
        default="tcp://127.0.0.1:10200",
        description="URI for the Wyoming server.",
    )
    """URI for the Wyoming server."""

    @field_validator("uri")
    @classmethod
    def validate_tcp_uri(cls, value: str) -> str:
        pattern = r"^tcp://([a-zA-Z0-9.-]+):([0-9]{1,5})$"
        match = re.match(pattern, value)
        if not match:
            raise ValueError(f"Invalid URI format: '{value}'. Expecting 'tcp://<host>:<port>'")
        host, port_str = match.groups()
        port = int(port_str)
        if port < 1 or port > 65535:
            raise ValueError(
                f"The network port must be in the range from 1 to 65535. Passed: {port}"
            )
        return value

    zeroconf: str = Field(
        default="silero-tts",
        description="Zeroconf discovery name. Empty string means disabled. Set to a name (e.g. 'silero-tts') to enable.",
    )
    """Zeroconf discovery name. Empty string means disabled. Set to a name (e.g. 'silero-tts') to enable."""

    streaming: bool = Field(
        default=True,
        description="Enable audio streaming.",
    )
    """Enable audio streaming."""

    inference_timeout: float = Field(
        default=5,
        ge=1,
        description="Timeout for inference of one sentence in seconds.",
    )
    """Timeout for inference of one sentence in seconds."""

    frame_duration_ms: float = Field(
        default=50,
        ge=1,
        description="Frame duration in milliseconds",
    )
    """Frame duration in milliseconds"""

    sample_rate: Literal[8000, 16000, 24000, 48000] = Field(
        default=48000,
        description="Audio sample rate in Hz for TTS output.",
    )
    """Audio sample rate in Hz for TTS output."""

    @field_validator("sample_rate", mode="before")
    @classmethod
    def coerce_sample_rate(cls, v: object) -> object:
        if isinstance(v, str):
            return int(v)
        return v

    max_models: int = Field(
        default=2,
        ge=1,
        description="Maximum number of models to cache in memory. Model with the lowest RPS rating is evicted when limit reached.",
    )
    """Maximum number of models to cache in memory. Model with the lowest RPS rating is evicted when limit reached."""

    cache_half_life: int = Field(
        default=60,
        ge=1,
        description="Period of downtime in seconds during which the model's RPS will be halved.",
    )
    """Period of downtime in seconds during which the model's RPS will be halved."""

    max_concurrent_sentences_per_model: int = Field(
        default=2,
        ge=1,
        description="Maximum concurrent sentences per model.",
    )
    """Maximum concurrent sentences per model."""

    max_sentence_chars: int = Field(
        default=140,
        ge=10,
        description="Maximum character count per text sentence for TTS processing.",
    )
    """Maximum character count per text sentence for TTS processing."""

    data_yml_path: str = Field(
        default="data/data.yml",
    )
    """Local path to the voice/model mapping configuration file data.yml"""

    models_dir: str = Field(
        default="models/silero",
        description="Directory for downloaded Silero .pt model files.",
    )
    """Directory for downloaded Silero .pt model files."""

    models_yml_url: HttpUrl = Field(
        default="https://raw.githubusercontent.com/snakers4/silero-models/refs/heads/master/models.yml",
        description="URL to the Silero models.yml registry file.",
    )
    """URL to the Silero models.yml registry file."""

    models_yml_hash: str = Field(
        default="",
        description="SHA-256 hash of the Silero models.yml file for integrity verification. Set empty to skip validation.",
    )
    """SHA-256 hash of the Silero models.yml file for integrity verification. Set empty to skip validation."""

    @field_validator("models_yml_hash")
    @classmethod
    def models_yml_hash_must_be_valid(cls, v: str) -> str:
        if v and not v.strip():
            return ""
        if v:
            import re

            if not re.fullmatch(r"[a-f0-9]{64}", v.lower()):
                raise ValueError(
                    "TTS_MODELS_YML_HASH must be a 64-character hex string or empty to skip validation"
                )
        return v

    silero: SileroSettings = Field(default_factory=SileroSettings)
    normalization: NormalizationSettings = Field(
        default_factory=NormalizationSettings,
    )
    openai: OpenAiSettings = Field(default_factory=OpenAiSettings)
    torch: TorchSettings = Field(default_factory=TorchSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        yaml_file="config.yml",
        yaml_file_encoding="utf-8",
        env_prefix="TTS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # CLI > ENV OS > config.yaml > Defaults
        return (
            CliArgsSource(settings_cls),
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            init_settings,
        )


class CliArgsSource(PydanticBaseSettingsSource):
    _fields_to_skip = ["normalization"]

    def get_field_value(self, field, field_name):
        return None

    def __call__(self) -> dict[str, Any]:
        return self._parse_cli_args()

    def _parse_cli_args(self) -> dict[str, Any]:  # noqa: C901
        parser = argparse.ArgumentParser(
            description=__metadata__["summary"],
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        schema = Settings.model_json_schema()
        properties = schema.get("properties", {})
        definitions = schema.get("$defs", {})

        cli_mapping: dict[str, list[str]] = {}

        def _add_field(prefix: list[str], field_name: str, sub_info: dict[str, Any]):
            full_prefix = "_".join(prefix) + "_" if prefix else ""
            cli_name = f"{full_prefix}{field_name}"

            for field_to_skip in self._fields_to_skip:
                if cli_name.startswith(field_to_skip):
                    return

            help_text = sub_info.get("description", "")
            type = sub_info.get("type")
            if type is None:
                return

            if type == "boolean":
                parser.add_argument(
                    f"--{cli_name}", action=argparse.BooleanOptionalAction, help=help_text
                )
            elif "enum" in sub_info:
                parser.add_argument(
                    f"--{cli_name}", type=str, choices=sub_info["enum"], help=help_text
                )
            else:
                parser.add_argument(f"--{cli_name}", metavar=type, type=str, help=help_text)

            cli_mapping[cli_name] = prefix

        def _add_fields(prefix: list[str], properties: dict[str, Any]):
            for field_name, field_info in properties.items():
                if "$ref" in field_info:
                    ref_name = field_info["$ref"].split("/")[-1]
                    sub_model = definitions.get(ref_name, {})
                    sub_properties = sub_model.get("properties", {})

                    if "enum" in sub_model:
                        _add_field(prefix=prefix, field_name=field_name, sub_info=sub_model)
                        continue

                    if prefix is None:
                        root_prefix = [field_name]
                    else:
                        root_prefix = prefix.copy()
                        root_prefix.append(field_name)

                    _add_fields(prefix=root_prefix, properties=sub_properties)
                else:
                    _add_field(prefix=prefix, field_name=field_name, sub_info=field_info)

        _add_fields(prefix=None, properties=properties)

        structured_data: dict[str, Any] = {}

        args, _ = parser.parse_known_args()
        raw_args = {k: v for k, v in vars(args).items() if v is not None}
        for key, value in raw_args.items():
            if key not in cli_mapping:
                continue

            prefix = cli_mapping[key]
            if not prefix:
                structured_data[key] = value
            else:
                data = structured_data
                for prefix_part in prefix:
                    if prefix_part not in data:
                        data[prefix_part] = {}
                    data = data[prefix_part]

                sub_key = key[len("_".join(prefix)) + 1 :]
                data[sub_key] = value

        return structured_data


@lru_cache
def get_settings() -> Settings:
    return Settings()
