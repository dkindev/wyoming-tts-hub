import os
from abc import ABC, abstractmethod
from pathlib import Path

import yaml
from loguru import logger

from src.tts.models import (
    EngineType,
    ModelInfo,
    NormalizationType,
    PredefinedData,
    Prompt,
    TextFormat,
    Voice,
    VoiceNormalization,
)


class DataStorage(ABC):
    @abstractmethod
    def get_voices(self) -> list[Voice]:
        ...

    @abstractmethod
    def get_voice(self, voice_id: str) -> Voice | None:
        ...

    @abstractmethod
    def get_model_info(self, model_id: str) -> ModelInfo | None:
        ...

    @abstractmethod
    def get_model_infos(self) -> list[ModelInfo]:
        ...

    @abstractmethod
    def get_prompt(self, prompt_id: str) -> Prompt | None:
        ...

    @abstractmethod
    def get_voice_normalization(
        self, voice_id: str, text_format: TextFormat, language: str
    ) -> VoiceNormalization | None:
        ...


class YamlDataStorage(DataStorage):
    def __init__(
        self,
        config_path_or_model: str | Path | PredefinedData,
        active_models: list[str] | None = None,
    ):
        if isinstance(config_path_or_model, str | Path):
            config_model = self._load_config_model(config_path_or_model)
        else:
            config_model = config_path_or_model

        self._check_active_models(config_model, active_models)

        config_model = self._filter_served(config_model, active_models)

        self._models: dict[str, ModelInfo] = {
            model_info.id: model_info for model_info in config_model.models
        }
        self._voices_by_id: dict[str, Voice] = {v.id: v for v in config_model.voices}
        self._prompts: dict[str, Prompt] = (
            {p.id: p for p in config_model.prompts} if config_model.prompts else {}
        )
        self._voice_normalizations: dict[str, VoiceNormalization] = (
            {
                f"{vn.voice_id}__{vn.text_format.value}__{vn.language}": vn
                for vn in config_model.voice_normalizations
            }
            if config_model.voice_normalizations
            else {}
        )

    def _load_config_model(self, config_path: str | Path) -> PredefinedData:
        config_path = str(config_path).strip()
        if not config_path:
            raise ValueError("Path to the model configuration file is empty or whitespace")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Models configuration file not found at path: '{config_path}'")

        logger.debug("Loading models configuration from '{path}'", path=config_path)

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._validate_sections(data, config_path)

        models_list: list[ModelInfo] = []
        voices_list: list[Voice] = []
        voice_normalizations_list: list[VoiceNormalization] = []
        seen_voice_ids: dict[str, str] = {}

        for model_id, model_data in (data.get("models") or {}).items():
            if not isinstance(model_data, dict):
                raise ValueError(
                    f"Model '{model_id}' must be a mapping of its fields, but it is a "
                    f"{type(model_data).__name__}"
                )

            models_list.append(self._parse_model_info(model_id, model_data))

            voices = model_data.get("voices")
            if voices is not None and not isinstance(voices, list):
                raise ValueError(
                    f"Model '{model_id}' must declare 'voices' as a list of voices, "
                    f"but it holds a {type(voices).__name__}"
                )

            for voice_entry in voices or []:
                voices_list.append(
                    self._parse_voice(
                        model_id, voice_entry, seen_voice_ids, voice_normalizations_list
                    )
                )

        prompts_list = self._parse_prompts(data)

        logger.debug("Configuration loaded.")
        return PredefinedData(
            models=models_list,
            voices=voices_list,
            prompts=prompts_list if prompts_list else None,
            voice_normalizations=voice_normalizations_list if voice_normalizations_list else None,
        )

    @staticmethod
    def _parse_model_info(model_id: str, model_data: dict) -> ModelInfo:
        """Read one model entry, refusing one that declares nothing speakable."""
        engine_type_value = model_data.get("engine_type")
        if engine_type_value is None:
            raise ValueError(
                f"Model '{model_id}' is missing required 'engine_type' "
                "(one of: silero, qwen, openai)"
            )
        try:
            engine_type = EngineType(engine_type_value)
        except ValueError:
            raise ValueError(
                f"Model '{model_id}' has unknown 'engine_type' '{engine_type_value}' "
                "(expected one of: silero, qwen, openai)"
            ) from None

        languages_raw = model_data.get("languages")
        if not languages_raw:
            raise ValueError(f"Model '{model_id}' must declare a non-empty 'languages' list")

        # A bare string would otherwise be read one character at a time.
        if not isinstance(languages_raw, list) or not all(
            isinstance(language, str) for language in languages_raw
        ):
            raise ValueError(
                f"Model '{model_id}' must declare 'languages' as a list of language codes, "
                "such as [ru]"
            )

        return ModelInfo(
            id=model_id,
            engine_type=engine_type,
            ssml_supported=model_data.get("ssml_supported", False),
            language_auto_detected=model_data.get("language_auto_detected", False),
            languages=[lang.strip() for lang in languages_raw],
            enabled=model_data.get("enabled", True),
            warmup=model_data.get("warmup", False),
            hash_prefix=model_data.get("hash_prefix") or None,
        )

    @staticmethod
    def _parse_voice(
        model_id: str,
        voice_entry: object,
        seen_voice_ids: dict[str, str],
        voice_normalizations_list: list[VoiceNormalization],
    ) -> Voice:
        """Read one voice of a model, refusing an entry that names no voice."""
        if not isinstance(voice_entry, dict):
            raise ValueError(
                f"A voice of model '{model_id}' must be a mapping of its fields, but it "
                f"is a {type(voice_entry).__name__}"
            )

        voice_name = voice_entry.get("name")
        if not isinstance(voice_name, str) or not voice_name.strip():
            raise ValueError(
                f"A voice of model '{model_id}' must declare a non-empty 'name', "
                f"but it holds {voice_entry.get('name')!r}"
            )

        voice_id = f"{model_id}-{voice_name}"
        if voice_id in seen_voice_ids:
            raise ValueError(
                f"Duplicate voice ID '{voice_id}': multiple voices in model "
                f"'{model_id}' share the name '{voice_name}'"
            )

        seen_voice_ids[voice_id] = model_id

        voice = Voice(
            id=voice_id,
            name=voice_name,
            # An absent speaker and an explicitly null one mean the same thing.
            speaker=(voice_entry.get("speaker") or "").strip() or voice_name,
            model_id=model_id,
            ref_audio=voice_entry.get("ref_audio") or None,
            ref_text=voice_entry.get("ref_text") or None,
            instruct=voice_entry.get("instruct") or None,
        )
        YamlDataStorage._parse_voice_normalization(voice_entry, voice_id, voice_normalizations_list)

        return voice

    @staticmethod
    def _validate_sections(data: object, config_path: str) -> None:
        """Refuse a document whose sections are not the shapes the parser reads.

        Without this, a mistyped file raises from inside the parse loop, naming nothing
        about the file that was wrong.
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"The model configuration file '{config_path}' must be a mapping of sections, "
                f"but it holds a {type(data).__name__}"
            )

        models_section = data.get("models")
        if models_section is not None and not isinstance(models_section, dict):
            raise ValueError(
                f"The 'models' section of '{config_path}' must be a mapping of model ids, "
                f"but it holds a {type(models_section).__name__}"
            )

        prompts_section = data.get("prompts")
        if prompts_section is not None and not isinstance(prompts_section, list):
            raise ValueError(
                f"The 'prompts' section of '{config_path}' must be a list of prompts, but it "
                f"holds a {type(prompts_section).__name__}"
            )

    @staticmethod
    def _parse_voice_normalization(
        voice_entry: dict,
        voice_id: str,
        voice_normalizations_list: list[VoiceNormalization],
    ) -> None:
        normalization = voice_entry.get("normalization")
        if not normalization:
            return

        if not isinstance(normalization, dict):
            raise ValueError(
                f"Voice '{voice_id}' must declare 'normalization' as a mapping of language to "
                f"text format, but it holds a {type(normalization).__name__}"
            )

        for language, formats in normalization.items():
            if not isinstance(formats, dict):
                raise ValueError(
                    f"Voice '{voice_id}' must declare 'normalization' per language, but "
                    f"'{language}' holds a {type(formats).__name__}"
                )

            for text_format_str, norm_data in formats.items():
                if not isinstance(norm_data, dict):
                    raise ValueError(
                        f"Voice '{voice_id}' must declare 'normalization.{language}."
                        f"{text_format_str}' as a mapping of its fields, but it holds a "
                        f"{type(norm_data).__name__}"
                    )

                try:
                    text_format = TextFormat(text_format_str)
                except ValueError:
                    continue
                enabled = norm_data.get("enabled", True)
                type_str = norm_data.get("type", "simple")
                try:
                    norm_type = NormalizationType(type_str)
                except ValueError:
                    norm_type = NormalizationType.SIMPLE
                prompt_id = norm_data.get("prompt_id")
                vn = VoiceNormalization(
                    voice_id=voice_id,
                    text_format=text_format,
                    language=language,
                    type=norm_type,
                    enabled=enabled,
                    prompt_id=prompt_id,
                )
                voice_normalizations_list.append(vn)

    @staticmethod
    def _parse_prompts(data: dict) -> list[Prompt]:
        prompts_list: list[Prompt] = []
        for index, prompt_entry in enumerate(data.get("prompts") or []):
            if not isinstance(prompt_entry, dict):
                raise ValueError(
                    f"A prompt in the 'prompts' section must be a mapping of its fields, but "
                    f"entry {index} is a {type(prompt_entry).__name__}"
                )

            for required in ("id", "text", "model"):
                if required not in prompt_entry:
                    raise ValueError(
                        f"A prompt in the 'prompts' section is missing its required "
                        f"'{required}' (entry {index})"
                    )

            prompt = Prompt(
                id=prompt_entry["id"],
                text=prompt_entry["text"],
                model=prompt_entry["model"],
            )
            prompts_list.append(prompt)
        return prompts_list

    @staticmethod
    def _check_active_models(config: PredefinedData, active_models: list[str] | None) -> None:
        if active_models is None:
            return
        declared_ids = {model_info.id for model_info in config.models}
        unknown_ids = sorted(set(active_models) - declared_ids)
        if unknown_ids:
            raise ValueError(
                f"active_models references unknown model id(s): {', '.join(unknown_ids)}"
            )

    @staticmethod
    def _filter_served(config: PredefinedData, active_models: list[str] | None) -> PredefinedData:
        allowed_ids = set(active_models) if active_models is not None else None

        served_models: list[ModelInfo] = []
        for model_info in config.models:
            if allowed_ids is not None and model_info.id not in allowed_ids:
                continue
            if not model_info.enabled:
                if allowed_ids is not None and model_info.id in allowed_ids:
                    logger.warning(
                        "Model '{model_id}' is listed in active_models but disabled "
                        "in the model config; it will not be served",
                        model_id=model_info.id,
                    )
                continue
            served_models.append(model_info)

        served_model_ids = {model_info.id for model_info in served_models}
        filtered_voices = [v for v in config.voices if v.model_id in served_model_ids]

        return PredefinedData(
            models=served_models,
            voices=filtered_voices,
            prompts=config.prompts,
            voice_normalizations=config.voice_normalizations,
        )

    def get_voices(self) -> list[Voice]:
        return list(self._voices_by_id.values())

    def get_voice(self, voice_id: str) -> Voice | None:
        return self._voices_by_id.get(voice_id)

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def get_model_infos(self) -> list[ModelInfo]:
        return list(self._models.values())

    def get_prompt(self, prompt_id: str) -> Prompt | None:
        return self._prompts.get(prompt_id)

    def get_voice_normalization(
        self, voice_id: str, text_format: TextFormat, language: str
    ) -> VoiceNormalization | None:
        return self._voice_normalizations.get(f"{voice_id}__{text_format.value}__{language}")
