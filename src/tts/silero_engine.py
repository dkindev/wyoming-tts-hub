import asyncio
import hashlib
import os
import urllib
from collections.abc import AsyncIterator
from typing import Any

import torch
import yaml
from loguru import logger

from src.tts.engine import TorchTtsEngine
from src.tts.models import ModelInfo, TextFormat, TtsResult, Voice


class SileroTtsEngine(TorchTtsEngine):
    def __init__(
        self,
        model_info: ModelInfo,
        device: str,
        sample_rate: int,
        models_dir: str,
        models_yml_url: str,
        models_yml_hash: str | None,
    ):
        super().__init__(model_info, device)

        self._sample_rate: int | None = None
        self._target_sample_rate = sample_rate
        self._models_dir = models_dir
        self._models_yml_url = models_yml_url
        self._models_yml_hash = models_yml_hash
        self._loaded_model: Any | None = None

    async def _synthesize_pcm(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        language: str | None = None,
    ) -> AsyncIterator[TtsResult]:
        tensor = await asyncio.to_thread(
            self._run_tts_sync,
            self._loaded_model,
            text,
            voice.speaker,
            self._sample_rate,
            text_format,
        )

        audio_tensor = (
            tensor.detach()
            .squeeze()
            .clamp(-1.0, 1.0)
            .mul(32767)
            .to(dtype=torch.int16, device="cpu")
        )

        yield TtsResult(
            audio=audio_tensor.numpy(),
            sample_rate=self._sample_rate,
            bytes_per_sample=2,
            channels=1,
        )

    def _release_resources(self) -> None:
        del self._loaded_model
        super()._release_resources()

    async def _warmup_on_device(
        self, device: torch.device, voices: list[Voice] | None = None
    ) -> bool:
        self._loaded_model = await asyncio.to_thread(
            self._warmup_on_device_sync, self._model_info, device
        )
        return True

    def _warmup_on_device_sync(self, model_info: ModelInfo, device: torch.device) -> Any:
        loaded_model, sample_rate, example_text, speakers = self._load_model(model_info, device)

        speaker, text = self._determine_warmup_params(loaded_model, example_text, speakers)

        logger.debug(
            "Silero model '{model_id}' is warming up. Speaker: '{speaker}' Text: '{text}'",
            model_id=model_info.id,
            speaker=speaker,
            text=text,
        )

        if speaker and text:
            self._run_tts_sync(loaded_model, text, speaker, sample_rate)

        self._sample_rate = sample_rate

        return loaded_model

    def _determine_warmup_params(
        self, loaded_model: Any, example_text: str, speakers: dict[str, str] | None
    ) -> tuple[str, str]:
        if speakers:
            speaker = next(iter(speakers))
            return speaker, speakers[speaker]

        speaker = loaded_model.speakers[0] if getattr(loaded_model, "speakers", None) else None

        return speaker, example_text

    def _run_tts_sync(
        self,
        loaded_model: Any,
        text: str,
        speaker: str,
        sample_rate: int,
        text_format: TextFormat = TextFormat.TEXT,
    ) -> torch.Tensor:
        with torch.inference_mode():
            audio = (
                loaded_model.apply_tts(ssml_text=text, speaker=speaker, sample_rate=sample_rate)
                if text_format == TextFormat.SSML
                else loaded_model.apply_tts(text=text, speaker=speaker, sample_rate=sample_rate)
            )

            return audio

    def _load_model(
        self, model_info: ModelInfo, device: torch.device
    ) -> tuple[Any, int, str, dict[str, str]]:
        """Loads and returns the Silero model, sample_rate, sample text, and speaker samples."""

        local_path, sample_rates, example_text, speakers = self._resolve_model_metadata(model_info)
        sample_rate = self._select_sample_rate(self._target_sample_rate, sample_rates)

        try:
            importer = torch.package.PackageImporter(local_path)
            pt_model = importer.load_pickle("tts_models", "model", map_location=device)
            # Ensure the model modules are shifted as well
            pt_model.to(device)

            return pt_model, sample_rate, example_text, speakers
        except Exception as e:
            raise RuntimeError(
                f"Failed to load model '{model_info.id}' with path: {local_path}. "
                f"Try to delete model to force a fresh download"
            ) from e

    def _resolve_model_metadata(
        self, model_info: ModelInfo
    ) -> tuple[str, list[int], str, dict[str, str]]:
        """Return the local path, sample rates, example text and speaker examples.

        Downloads the Silero models.yml file and the model itself if they are not available locally.
        """
        models_dir = self._models_dir

        yml_path = os.path.join(models_dir, "silero", "models.yml")
        registry = self._get_models_data(yml_path, self._models_yml_url, self._models_yml_hash)

        tts_models = registry.get("tts_models", {})
        language = self._resolve_internal_model_language(tts_models, model_info, yml_path)

        lang_dir = os.path.join(models_dir, "silero", language)
        os.makedirs(lang_dir, exist_ok=True)

        upstream_id = self._upstream_id(model_info)
        model_entry = tts_models[language][upstream_id]
        latest = model_entry.get("latest", {})
        sample_rates = latest.get("sample_rate", [])
        example_text = latest.get("example", "")
        raw_speakers = latest.get("speakers", {})
        speakers = {name: s.get("example", "") for name, s in raw_speakers.items()}

        model_path = os.path.join(lang_dir, f"{upstream_id}.pt")
        if os.path.isfile(model_path):
            logger.debug(
                "Model '{model}' found at path '{path}'", model=model_info.id, path=model_path
            )
            return model_path, sample_rates, example_text, speakers

        package_url = latest.get("package")
        if not package_url:
            raise RuntimeError(
                f"Model '{model_info.id}' for language '{language}' not found in configuration file. "
                f"Delete '{yml_path}' to force a fresh download"
            )

        logger.debug(
            "Model '{model}' not found. Attempting to load from '{url}'",
            model=model_info.id,
            url=package_url,
        )

        try:
            torch.hub.download_url_to_file(
                package_url, model_path, hash_prefix=model_info.hash_prefix
            )
        except Exception as e:
            if os.path.isfile(model_path):
                os.remove(model_path)
            raise RuntimeError(
                f"Failed to download model '{model_info.id}' for language '{language}'"
            ) from e

        logger.debug(
            "Model '{model}' is saved in the file '{path}'", model=model_info.id, path=model_path
        )

        return model_path, sample_rates, example_text, speakers

    @staticmethod
    def _upstream_id(model_info: ModelInfo) -> str:
        """The registry key and file name to resolve, falling back to the local id."""
        return (model_info.upstream_id or "").strip() or model_info.id

    @staticmethod
    def _resolve_internal_model_language(
        tts_models: dict, model_info: ModelInfo, yml_path: str
    ) -> str:
        """Return the registry section (keyed by language) that owns the model.

        Prefers the model's sole declared Language when it owns the model, then
        falls back to scanning every section. Raises RuntimeError when no
        section owns the model.
        """
        upstream_id = SileroTtsEngine._upstream_id(model_info)
        declared_languages = model_info.languages

        if len(declared_languages) == 1:
            declared = declared_languages[0]
            if upstream_id in tts_models.get(declared, {}):
                return declared

        for section, section_models in tts_models.items():
            if upstream_id in section_models:
                return section

        raise RuntimeError(
            f"Model '{model_info.id}' not found in the Silero models registry '{yml_path}'. "
            f"Delete '{yml_path}' to force a fresh download"
        )

    @staticmethod
    def _get_models_data(yml_path: str, models_yml_url: str, models_yml_hash: str | None) -> dict:
        def load_yaml() -> dict:
            try:
                with open(yml_path, encoding="utf-8") as f:
                    logger.debug("Loading the models configuration file '{path}'", path=yml_path)
                    models_config = yaml.safe_load(f)
                    logger.debug("Models configuration loaded")
                    return models_config
            except Exception as e:
                raise RuntimeError(
                    f"Failed to parse the models configuration file: {e}. Delete '{yml_path}' to force a fresh download"
                ) from e

        if os.path.exists(yml_path):
            if models_yml_hash:
                hasher = hashlib.sha256()
                with open(yml_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                local_hash = hasher.hexdigest().lower()

                if local_hash == models_yml_hash:
                    return load_yaml()
                else:
                    logger.warning(
                        "Models configuration file '{path}' is corrupted or outdated. Redownloading..."
                    )
            else:
                logger.debug(
                    "Models configuration file hash validation skipped (models_yml_hash is None)"
                )
                return load_yaml()
        else:
            logger.debug(
                "Models configuration file not found at '{path}'",
                path=yml_path,
            )

        logger.debug("Attempting to load model configuration from '{url}'", url=models_yml_url)
        SileroTtsEngine._download_models_yml(yml_path, models_yml_url, models_yml_hash)
        logger.debug("Models configuration are saved in the file '{path}'", path=yml_path)

        return load_yaml()

    @staticmethod
    def _download_models_yml(file_path: str, models_yml_url: str, models_yml_hash: str | None):
        try:
            if not models_yml_hash:
                urllib.request.urlretrieve(models_yml_url, file_path)
                return

            hasher = hashlib.sha256()
            with urllib.request.urlopen(models_yml_url) as response:
                with open(file_path, "wb") as file:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        file.write(chunk)
                        hasher.update(chunk)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download the models configuration from '{models_yml_url}'"
            ) from e

        downloaded_hash = hasher.hexdigest().lower()
        if downloaded_hash != models_yml_hash:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise RuntimeError(
                f"Error verifying hash of model configuration file loaded at '{models_yml_url}'"
            )

    @staticmethod
    def _select_sample_rate(config_rate: int, supported_rates: list[int]) -> int:
        if not supported_rates:
            return config_rate

        unique_rates = sorted(set(supported_rates))

        if len(unique_rates) == 1:
            return unique_rates[0]

        max_rate = unique_rates[-1]
        if config_rate > max_rate:
            return max_rate
        min_rate = unique_rates[0]
        if config_rate < min_rate:
            return min_rate

        if config_rate in unique_rates:
            return config_rate

        candidates = [r for r in unique_rates if r < config_rate]
        if candidates:
            return candidates[-1]

        return max_rate
