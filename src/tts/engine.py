import asyncio
import gc
import hashlib
import os
import urllib.request
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
import yaml
from loguru import logger

from src.tts.cache import ExponentialDecayCache
from src.tts.config_storage import SileroTTSConfigStorage
from src.tts.exceptions import TTSEngineError
from src.tts.models import Model, NormalizationOptions, TextFormat, TTSConfig, TTSResult, Voice
from src.tts.preprocessing import TextNormalizerFactory, TextSentenizerFactory

BYTES_PER_SAMPLE = 2
CHANNELS = 1


@dataclass
class CachedModel:
    """Bundles a loaded model with its sample rate and concurrency control."""

    model: Any
    sample_rate: int
    semaphore: asyncio.Semaphore


class SileroTTSEngine:
    """TTS engine wrapping Silero TTS library."""

    def __init__(
        self,
        config: TTSConfig,
        storage: SileroTTSConfigStorage,
        text_sentenizer_factory: TextSentenizerFactory,
        text_normalizer_factory: TextNormalizerFactory,
    ):
        self._config = config
        self._storage = storage
        self._cache = ExponentialDecayCache(
            capacity=self._config.max_models,
            half_life_seconds=self._config.cache_half_life,
            eviction_interval=5.0,
            on_evict=self._clear_cached_models,
        )
        self._device = self._resolve_device(config.device)
        self._lock: asyncio.Lock | None = None
        self._text_sentenizer_factory = text_sentenizer_factory
        self._text_normalizer_factory = text_normalizer_factory

    async def synthesize_pcm_chunks(
        self,
        text: str,
        voice_id: str,
        text_format: TextFormat,
    ) -> AsyncIterator[TTSResult]:
        if text_format not in self.get_supported_text_formats():
            raise TTSEngineError(f"Invalid text format: {text_format}")

        text = text.strip()
        if not text:
            raise TTSEngineError("Text is empty or whitespace")

        voice = self._storage.get_voice(voice_id)
        if voice is None:
            raise TTSEngineError(f"Unsupported voice: {voice_id}")

        model = self._storage.get_model(voice.model)
        if model is None:
            raise TTSEngineError(f"Unsupported model: {voice.model}")

        logger.info(
            "Synthesizing TTS. Text length: {text_length}. Voice: {voice_id}. Text format: {text_format}. Model: {model_name}",
            text_length=len(text),
            voice_id=voice_id,
            text_format=text_format.value,
            model_name=model.name,
        )

        cached = await self._get_tts_model(model)

        sentences = self._text_to_sentences(
            text=text,
            voice=voice,
            text_format=text_format,
            normalization_options=NormalizationOptions(
                voice=voice, model=model, silero_model=cached.model
            ),
        )

        async for chunk in self._synthesize_pcm_chunks(
            sentences=sentences, cached_model=cached, voice=voice, text_format=text_format
        ):
            yield chunk

    async def warmup(self):
        """Warm up the models."""
        if self._cache:
            return

        async with self._get_lock():
            if self._cache:
                return

            logger.info("Warming up engine")

            models = self._storage.get_models()
            to_warm = [model for model in models if model.warmup][: self._config.max_models]

            logger.debug("Models to warm up: {count}", count=len(to_warm))

            for model in to_warm:
                await self._warmup_tts_model(model)

            logger.info("Engine has been warmed up")

    def get_storage(self) -> SileroTTSConfigStorage:
        """Return the config storage."""
        return self._storage

    def get_supported_text_formats(self) -> tuple[TextFormat, ...]:
        """Return supported text formats."""
        return tuple(TextFormat)

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

    async def _text_to_sentences(
        self,
        text: str,
        voice: Voice,
        text_format: TextFormat,
        normalization_options: NormalizationOptions,
    ) -> AsyncIterator[str]:
        text_sentenizer = self._text_sentenizer_factory.create_text_sentenizer(
            voice=voice, format=text_format
        )
        if text_sentenizer is None:
            raise TTSEngineError(
                f"Text sentenizer not found for '{voice.locale}' locale and '{text_format.value}' format"
            )

        logger.debug(
            "Convert text into sentences using '{text_sentenizer}'",
            text_sentenizer=text_sentenizer.__class__.__name__,
        )

        sentences = text_sentenizer.text_to_sentences(
            text=text, max_sentence_chars=self._config.max_sentence_chars
        )

        text_normalizer = (
            self._text_normalizer_factory.create_text_normalizer(voice=voice, format=text_format)
            if self._text_normalizer_factory is not None
            else None
        )

        if text_normalizer is None:
            for sentence in sentences:
                yield sentence
        else:
            logger.debug(
                "Normalize text using '{text_normalizer}'",
                text_normalizer=text_normalizer.__class__.__name__,
            )

            normalized_sentences = text_normalizer.normalize_text(
                sentences=sentences,
                options=normalization_options,
            )

            async for sentence in normalized_sentences:
                yield sentence

    async def _synthesize_pcm_chunks(
        self,
        sentences: AsyncIterator[str],
        cached_model: CachedModel,
        voice: Voice,
        text_format: TextFormat,
    ) -> AsyncIterator[TTSResult]:
        queue = asyncio.Queue(maxsize=10)
        active_tasks = set()

        producer_task = asyncio.create_task(
            self._queue_sentences(
                sentences=sentences,
                cached_model=cached_model,
                voice=voice,
                text_format=text_format,
                queue=queue,
                active_tasks=active_tasks,
            )
        )

        active_tasks.add(producer_task)
        producer_task.add_done_callback(active_tasks.discard)

        try:
            while True:
                future = await queue.get()
                if future is None:
                    queue.task_done()
                    break

                try:
                    buffer = await future

                    for chunk in self._generate_chunks(
                        buffer=buffer,
                        sample_rate=cached_model.sample_rate,
                    ):
                        yield chunk

                    logger.debug("Audio frames has been sent.")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    raise TTSEngineError("Sentence inference error") from e
                finally:
                    queue.task_done()
        finally:
            tasks_to_cancel = [task for task in active_tasks if not task.done()]

            for task in tasks_to_cancel:
                task.cancel()

            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    async def _queue_sentences(
        self,
        sentences: AsyncIterator[str],
        cached_model: CachedModel,
        voice: Voice,
        text_format: TextFormat,
        queue: asyncio.Queue,
        active_tasks: set,
    ):
        loop = asyncio.get_running_loop()

        try:
            async for sentence in sentences:
                future = loop.create_future()

                await queue.put(future)

                logger.debug("Sentence queued for inferencing. Text: {sentence}", sentence=sentence)

                task = asyncio.create_task(
                    self._process_sentence(sentence, cached_model, voice, text_format, future)
                )

                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)

        finally:
            # Completion marker
            await queue.put(None)

    async def _process_sentence(
        self,
        sentence: str,
        cached_model: CachedModel,
        voice: Voice,
        text_format: TextFormat,
        future: asyncio.Future,
    ) -> np.ndarray:
        try:
            async with cached_model.semaphore:
                tensor = await asyncio.wait_for(
                    asyncio.to_thread(
                        SileroTTSEngine._run_tts_sync,
                        cached_model,
                        sentence,
                        voice.speaker,
                        text_format,
                    ),
                    timeout=self._config.inference_timeout,
                )

                if not future.cancelled():
                    audio_tensor = (
                        tensor.detach()
                        .squeeze()
                        .clamp(-1.0, 1.0)
                        .mul(32767)
                        .to(dtype=torch.int16, device="cpu")
                    )

                    future.set_result(audio_tensor.numpy())
        except Exception as e:
            if not future.cancelled():
                future.set_exception(e)

    def _generate_chunks(
        self,
        buffer: np.ndarray,
        sample_rate: int,
    ) -> Iterator[TTSResult]:
        duration_sec = self._config.frame_duration / 1000.0
        chunk_size = int(sample_rate * BYTES_PER_SAMPLE * CHANNELS * duration_sec)

        sample_frame_size = BYTES_PER_SAMPLE * CHANNELS
        chunk_size = (chunk_size // sample_frame_size) * sample_frame_size
        chunk_size = max(chunk_size, sample_frame_size)
        total_samples = buffer.shape[0]

        for i in range(0, total_samples, chunk_size):
            yield TTSResult(
                audio=buffer[i : i + chunk_size].tobytes(),
                sample_rate=sample_rate,
                bytes_per_sample=BYTES_PER_SAMPLE,
                channels=CHANNELS,
            )

    @staticmethod
    def _run_tts_sync(
        cached_model: CachedModel,
        text: str,
        speaker: str,
        text_format: TextFormat = TextFormat.TEXT,
    ) -> torch.Tensor:
        with torch.inference_mode():
            logger.debug(
                "Synthesizing TTS. Speaker: {speaker}. Sample rate: {sample_rate}. Type: {type}. Text: {text}",
                speaker=speaker,
                sample_rate=cached_model.sample_rate,
                type=text_format.value,
                text=text,
            )

            audio = (
                cached_model.model.apply_tts(
                    ssml_text=text, speaker=speaker, sample_rate=cached_model.sample_rate
                )
                if text_format == TextFormat.SSML
                else cached_model.model.apply_tts(
                    text=text, speaker=speaker, sample_rate=cached_model.sample_rate
                )
            )

            logger.debug("TTS synthesized on device '{device}'", device=audio.device.type)

            return audio

    async def shutdown(self):
        """Clears the model cache and forces VRAM to be released."""
        if not self._cache:
            return

        async with self._get_lock():
            if not self._cache:
                return

            logger.info("Cleaning engine resources.")

            await self._cache.close()

            logger.info("Engine resources have been cleared")

    async def _get_tts_model(self, model: Model) -> CachedModel:
        async with self._get_lock():
            cached = self._cache.get(model.name)
            if cached is None:
                logger.debug("Model '{name}' not found in cache", name=model.name)
                cached = await self._warmup_tts_model(model)
            else:
                logger.debug("Model '{name}' found in cache", name=model.name)

        return cached

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _clear_cached_models(self, items: list[tuple[str, CachedModel]]):
        logger.debug("Freeing up models resources. Models count: {count}", count=len(items))

        for item in items:
            model_name = item[0]
            cached_model = item[1]

            logger.debug("Freeing up model '{model}' resources", model=model_name)

            del cached_model.model
            del cached_model.semaphore
            del cached_model
            del item

            logger.debug("Model '{model}' resources was removed", model=model_name)

        gc.collect()

        if self._device.type == "cuda":
            torch.cuda.empty_cache()
        elif self._device.type == "mps":
            torch.mps.empty_cache()
        elif self._device.type == "xpu":
            torch.xpu.empty_cache()

        logger.debug("Models resources was removed")

    def _resolve_tts_model(self, model: Model) -> tuple[str, list[int], str, dict[str, str]]:
        """Return the local path, sample rates, example text and speaker examples.

        Downloads the Silero models.yml file and the model itself if they are not available locally.
        Raises TTSEngineError on failure.
        """
        logger.debug(
            "Trying to resolve model '{model}'",
            model=model.name,
        )

        language = model.language
        if not language:
            raise TTSEngineError(f"Language isn't specified for Silero model: {model.name}")

        models_dir = self._config.models_dir

        lang_dir = os.path.join(models_dir, "silero", language)
        os.makedirs(lang_dir, exist_ok=True)

        yml_path = os.path.join(models_dir, "silero", "models.yml")
        registry = self._get_models_data(
            yml_path, self._config.models_yml_url, self._config.models_yml_hash
        )

        tts_models = registry.get("tts_models", {})
        lang_models = tts_models.get(language, {})
        model_entry = lang_models.get(model.name, {})
        latest = model_entry.get("latest", {})
        sample_rates = latest.get("sample_rate", [])
        example_text = latest.get("example", "")
        raw_speakers = latest.get("speakers", {})
        speakers = {name: s.get("example", "") for name, s in raw_speakers.items()}

        model_path = os.path.join(lang_dir, f"{model.name}.pt")
        if os.path.isfile(model_path):
            logger.debug(
                "Model '{model}' found at path '{path}'", model=model.name, path=model_path
            )
            return model_path, sample_rates, example_text, speakers

        package_url = latest.get("package")
        if not package_url:
            raise TTSEngineError(
                f"Model '{model.name}' for language '{language}' not found in configuration file. "
                f"Delete '{yml_path}' to force a fresh download"
            )

        logger.debug(
            "Model '{model}' not found. Attempting to load from '{url}'",
            model=model.name,
            url=package_url,
        )

        try:
            torch.hub.download_url_to_file(package_url, model_path, hash_prefix=model.hash_prefix)
        except Exception as e:
            if os.path.isfile(model_path):
                os.remove(model_path)
            raise TTSEngineError(
                f"Failed to download model '{model.name}' for language '{language}'"
            ) from e

        logger.debug(
            "Model '{model}' is saved in the file '{path}'", model=model.name, path=model_path
        )

        return model_path, sample_rates, example_text, speakers

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
        SileroTTSEngine._download_models_yml(yml_path, models_yml_url, models_yml_hash)
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

    async def _load_tts_model(self, model: Model) -> tuple[CachedModel, str, dict[str, str]]:
        """Loads the model into the cache and returns the cached model, sample text, and speaker samples."""

        # Move blocking disk reading and heavy PyTorch initialization to a separate thread
        def _sync_load():
            local_path, sample_rates, example_text, speakers = self._resolve_tts_model(model)
            try:
                logger.debug(
                    "Loading model '{model}' to '{device}'",
                    model=model.name,
                    device=self._device.type,
                )

                importer = torch.package.PackageImporter(local_path)
                pt_model = importer.load_pickle("tts_models", "model", map_location=self._device)
                # Ensure the model modules are shifted as well
                pt_model.to(self._device)

                logger.debug(
                    "Model '{model}' loaded to '{device}'",
                    model=model.name,
                    device=self._device.type,
                )

                return pt_model, sample_rates, example_text, speakers
            except Exception as e:
                raise TTSEngineError(
                    f"Failed to load model '{model.name}' with path: {local_path}. "
                    f"Try to delete model to force a fresh download"
                ) from e

        tts_model, sample_rates, example_text, speakers = await asyncio.to_thread(_sync_load)

        sample_rate = self._select_sample_rate(self._config.sample_rate, sample_rates)
        semaphore = asyncio.Semaphore(self._config.max_concurrent_sentences_per_model)
        cached = CachedModel(tts_model, sample_rate, semaphore)

        self._cache.put(model.name, cached)

        logger.debug(
            "Model '{model}' was cached. Sample rate: '{sample_rate}'",
            model=model.name,
            sample_rate=sample_rate,
        )

        return cached, example_text, speakers

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

    async def _warmup_tts_model(self, model: Model) -> CachedModel:
        cached, example_text, speakers = await self._load_tts_model(model)

        if speakers:
            speaker = next(iter(speakers))
            text = speakers[speaker]
        else:
            speaker = cached.model.speakers[0]
            text = example_text

        logger.debug(
            "Model '{model}' is warming up. Speaker: '{speaker}' Text: '{text}'",
            model=model.name,
            speaker=speaker,
            text=text,
        )

        try:
            await asyncio.to_thread(self._run_tts_sync, cached, text, speaker)
            logger.debug("Model '{model}' has been warmed up.", model=model.name)
        except Exception:
            logger.exception("Failed to warm up the model '{model}'", model=model.name)

        return cached
