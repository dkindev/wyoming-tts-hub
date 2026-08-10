import os
from abc import ABC, abstractmethod
from pathlib import Path

import yaml
from loguru import logger

from src.tts.models import (
    Model,
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
    def get_model(self, model_id: str) -> Model | None:
        ...

    @abstractmethod
    def get_models(self) -> list[Model]:
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
    def __init__(self, config_path_or_model: str | Path | PredefinedData):
        if isinstance(config_path_or_model, str | Path):
            config_model = self._load_config_model(config_path_or_model)
        else:
            config_model = config_path_or_model

        config_model = self._filter_enabled(config_model)

        self._models: dict[str, Model] = {m.id: m for m in config_model.models}
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
        config_path = config_path.strip()
        if not config_path:
            raise ValueError("Path to the model configuration file is empty or whitespace")

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Models configuration file not found at path: '{config_path}'")

        logger.debug("Loading models configuration from '{path}'", path=config_path)

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        models_list: list[Model] = []
        voices_list: list[Voice] = []
        voice_normalizations_list: list[VoiceNormalization] = []

        for model_id, model_data in data.get("models", {}).items():
            models_list.append(
                Model(
                    id=model_id,
                    enabled=model_data.get("enabled", True),
                    warmup=model_data.get("warmup", False),
                    hash_prefix=model_data.get("hash_prefix") or None,
                )
            )

            for voice_entry in model_data.get("voices", []):
                voice_name = voice_entry["name"]
                speaker = voice_entry.get("speaker", "").strip() or voice_name
                voice_id = f"{model_id}-{voice_name}"
                voices_list.append(
                    Voice(
                        id=voice_id,
                        name=voice_name,
                        speaker=speaker,
                        model_id=model_id,
                        ref_audio=voice_entry.get("ref_audio") or None,
                        ref_text=voice_entry.get("ref_text") or None,
                        instruct=voice_entry.get("instruct") or None,
                    )
                )
                self._parse_voice_normalization(voice_entry, voice_id, voice_normalizations_list)

        prompts_list = self._parse_prompts(data)

        logger.debug("Configuration loaded.")
        return PredefinedData(
            models=models_list,
            voices=voices_list,
            prompts=prompts_list if prompts_list else None,
            voice_normalizations=voice_normalizations_list if voice_normalizations_list else None,
        )

    @staticmethod
    def _parse_voice_normalization(
        voice_entry: dict,
        voice_id: str,
        voice_normalizations_list: list[VoiceNormalization],
    ) -> None:
        normalization = voice_entry.get("normalization")
        if not normalization or not isinstance(normalization, dict):
            return
        for language, formats in normalization.items():
            if not isinstance(formats, dict):
                continue
            for text_format_str, norm_data in formats.items():
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
        for prompt_entry in data.get("prompts", []):
            prompt = Prompt(
                id=prompt_entry["id"],
                text=prompt_entry["text"],
                model=prompt_entry["model"],
            )
            prompts_list.append(prompt)
        return prompts_list

    @staticmethod
    def _filter_enabled(config: PredefinedData) -> PredefinedData:
        enabled_models = [m for m in config.models if m.enabled]
        enabled_model_ids = {m.id for m in enabled_models}

        filtered_voices = [v for v in config.voices if v.model_id in enabled_model_ids]

        return PredefinedData(
            models=enabled_models,
            voices=filtered_voices,
            prompts=config.prompts,
            voice_normalizations=config.voice_normalizations,
        )

    def get_voices(self) -> list[Voice]:
        return list(self._voices_by_id.values())

    def get_voice(self, voice_id: str) -> Voice | None:
        return self._voices_by_id.get(voice_id)

    def get_model(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    def get_models(self) -> list[Model]:
        return list(self._models.values())

    def get_prompt(self, prompt_id: str) -> Prompt | None:
        return self._prompts.get(prompt_id)

    def get_voice_normalization(
        self, voice_id: str, text_format: TextFormat, language: str
    ) -> VoiceNormalization | None:
        return self._voice_normalizations.get(f"{voice_id}__{text_format.value}__{language}")
