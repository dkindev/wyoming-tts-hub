import asyncio
import hashlib
import os
import urllib
from collections.abc import AsyncIterator
from typing import Any

import torch
import yaml
from loguru import logger

from src.tts.engine import TtsEngine
from src.tts.exceptions import TTSEngineError
from src.tts.models import Model, TextFormat, TtsResult, Voice


class SileroTtsEngine(TtsEngine):
    def __init__(
        self,
        model: Model,
        device: str,
        sample_rate: int,
        models_dir: str,
        models_yml_url: str,
        models_yml_hash: str | None,
    ):
        self._model = model
        self._device = device
        self._sample_rate = sample_rate
        self._models_dir = models_dir
        self._models_yml_url = models_yml_url
        self._models_yml_hash = models_yml_hash
        self._supported_text_formats = self._get_supported_text_formats(model)

        self._cached: Any | None = None
        self._lock: asyncio.Lock | None = None

    async def synthesize_pcm(
        self, text: str, voice: Voice, text_format: TextFormat, language: str | None = None
    ) -> AsyncIterator[TtsResult]:
        if text_format not in self._supported_text_formats:
            raise TTSEngineError(f"Invalid text format: {text_format}")

        text = text.strip()
        if not text:
            raise TTSEngineError("Text is empty or whitespace")

        if not voice:
            raise TTSEngineError("Voice cannot be null")

        if not language:
            languages = self._model.languages
            if not languages or len(languages) > 1:
                raise TTSEngineError("Language cannot be null")

            language = languages[0]

        if not self._cached:
            await self._warmup_model()

        tensor = await asyncio.to_thread(self._run_tts_sync, text, voice.speaker, text_format)

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

    async def warmup(self) -> None:
        """Warm up the engine."""
        if not self._model.warmup:
            return

        if self._cached:
            return

        logger.debug("Warming up engine")
        await self._warmup_model()
        logger.debug("Engine has been warmed up")

    async def close(self) -> None:
        del self._cached
        self._cached = None

    async def _warmup_model(self) -> None:
        if self._cached:
            return

        async with self._get_lock():
            if self._cached:
                return

            model, sample_rate, example_text, speakers = await asyncio.to_thread(
                self._load_model, self._model
            )

            self._cached = model
            self._sample_rate = sample_rate

            if speakers:
                speaker = next(iter(speakers))
                text = speakers[speaker]
            else:
                speaker = model.speakers[0]
                text = example_text

            logger.debug(
                "Model '{model}' is warming up. Speaker: '{speaker}' Text: '{text}'",
                model=self._model.id,
                speaker=speaker,
                text=text,
            )

            try:
                await asyncio.to_thread(self._run_tts_sync, text, speaker)
                logger.debug("Model '{model}' has been warmed up.", model=self._model.id)
            except Exception:
                logger.error("Failed to warm up the model '{model}'", model=self._model.id)

                raise

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @staticmethod
    def _get_supported_text_formats(model: Model) -> tuple[TextFormat, ...]:
        supported_text_formats = [TextFormat.TEXT]

        if model.ssml_supported:
            supported_text_formats.append(TextFormat.SSML)

        return supported_text_formats

    def _run_tts_sync(
        self,
        text: str,
        speaker: str,
        text_format: TextFormat = TextFormat.TEXT,
    ) -> torch.Tensor:
        with torch.inference_mode():
            logger.debug(
                "Synthesizing TTS. Speaker: {speaker}. Sample rate: {sample_rate}. Type: {type}. Text: {text}",
                speaker=speaker,
                sample_rate=self._sample_rate,
                type=text_format.value,
                text=text,
            )

            audio = (
                self._cached.apply_tts(
                    ssml_text=text, speaker=speaker, sample_rate=self._sample_rate
                )
                if text_format == TextFormat.SSML
                else self._cached.apply_tts(
                    text=text, speaker=speaker, sample_rate=self._sample_rate
                )
            )

            logger.debug("TTS synthesized on device '{device}'", device=audio.device.type)

            return audio

    def _load_model(self, model: Model) -> tuple[Any, int, str, dict[str, str]]:
        """Loads and returns the Silero model, sample_rate, sample text, and speaker samples."""

        local_path, sample_rates, example_text, speakers = self._resolve_model_metadata(model)
        sample_rate = self._select_sample_rate(self._sample_rate, sample_rates)
        device = self._resolve_device(self._device)

        try:
            logger.debug(
                "Loading model '{model}' to '{device}'",
                model=model.id,
                device=device.type,
            )

            importer = torch.package.PackageImporter(local_path)
            pt_model = importer.load_pickle("tts_models", "model", map_location=device)
            # Ensure the model modules are shifted as well
            pt_model.to(device)

            logger.debug(
                "Model '{model}' loaded to '{device}'",
                model=model.id,
                device=device.type,
            )

            return pt_model, sample_rate, example_text, speakers
        except Exception as e:
            raise TTSEngineError(
                f"Failed to load model '{model.id}' with path: {local_path}. "
                f"Try to delete model to force a fresh download"
            ) from e

    def _resolve_model_metadata(self, model: Model) -> tuple[str, list[int], str, dict[str, str]]:
        """Return the local path, sample rates, example text and speaker examples.

        Downloads the Silero models.yml file and the model itself if they are not available locally.
        Raises TTSEngineError on failure.
        """
        logger.debug(
            "Trying to resolve model '{model}'",
            model=model.id,
        )

        models_dir = self._models_dir

        yml_path = os.path.join(models_dir, "silero", "models.yml")
        registry = self._get_models_data(yml_path, self._models_yml_url, self._models_yml_hash)

        tts_models = registry.get("tts_models", {})
        language = self._resolve_internal_model_language(tts_models, model)

        lang_dir = os.path.join(models_dir, "silero", language)
        os.makedirs(lang_dir, exist_ok=True)

        model_entry = tts_models[language][model.id]
        latest = model_entry.get("latest", {})
        sample_rates = latest.get("sample_rate", [])
        example_text = latest.get("example", "")
        raw_speakers = latest.get("speakers", {})
        speakers = {name: s.get("example", "") for name, s in raw_speakers.items()}

        model_path = os.path.join(lang_dir, f"{model.id}.pt")
        if os.path.isfile(model_path):
            logger.debug("Model '{model}' found at path '{path}'", model=model.id, path=model_path)
            return model_path, sample_rates, example_text, speakers

        package_url = latest.get("package")
        if not package_url:
            raise TTSEngineError(
                f"Model '{model.id}' for language '{language}' not found in configuration file. "
                f"Delete '{yml_path}' to force a fresh download"
            )

        logger.debug(
            "Model '{model}' not found. Attempting to load from '{url}'",
            model=model.id,
            url=package_url,
        )

        try:
            torch.hub.download_url_to_file(package_url, model_path, hash_prefix=model.hash_prefix)
        except Exception as e:
            if os.path.isfile(model_path):
                os.remove(model_path)
            raise TTSEngineError(
                f"Failed to download model '{model.id}' for language '{language}'"
            ) from e

        logger.debug(
            "Model '{model}' is saved in the file '{path}'", model=model.id, path=model_path
        )

        return model_path, sample_rates, example_text, speakers

    @staticmethod
    def _resolve_internal_model_language(tts_models: dict, model: Model) -> str:
        """Return the registry section (keyed by language) that owns the model.

        Prefers the model's sole declared Language when it owns the model, then
        falls back to scanning every section. Raises TTSEngineError when no
        section owns the model.
        """
        declared_languages = model.languages

        if len(declared_languages) == 1:
            declared = declared_languages[0]
            if model.id in tts_models.get(declared, {}):
                return declared

        for section, section_models in tts_models.items():
            if model.id in section_models:
                return section

        raise TTSEngineError(
            f"Model '{model.id}' not found in the Silero models registry. "
            f"Delete the cached 'models.yml' to force a fresh download"
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
                raise TTSEngineError(
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
            raise TTSEngineError(
                f"Failed to download the models configuration from '{models_yml_url}'"
            ) from e

        downloaded_hash = hasher.hexdigest().lower()
        if downloaded_hash != models_yml_hash:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise TTSEngineError(
                f"Error verifying hash of model configuration file loaded at '{models_yml_url}'"
            )

    @staticmethod
    def _select_sample_rate(config_rate: int, supported_rates: list[int]) -> int:
        if not supported_rates:
            return config_rate
        if supported_rates is None:
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

    @staticmethod
    def _resolve_device(target_device_str: str) -> torch.device:
        try:
            device = torch.device(target_device_str)
        except RuntimeError:
            logger.warning(
                "Invalid device string '{device}'. Falling back to cpu.", device=target_device_str
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
