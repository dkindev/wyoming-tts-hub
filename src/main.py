import asyncio
import signal
from functools import partial

from loguru import logger
from openai import AsyncOpenAI
from wyoming.server import AsyncServer, AsyncTcpServer

from src.config import NormalizationSettings, OpenAiSettings, Settings, get_settings
from src.handler import TtsEngineHubEventHandler
from src.logger import setup_logging
from src.tts.data_storage import YamlDataStorage
from src.tts.engine_factory import TtsEngineFactory
from src.tts.engine_hub import TtsEngineHub
from src.tts.engine_manager import TtsEngineManager
from src.tts.middleware import (
    NormalizeTextMiddleware,
    ResolveLanguageMiddleware,
    SplitSentencesMiddleware,
)
from src.tts.models import BackendType
from src.tts.preprocessing import (
    TextNormalizerFactory,
    TextSentencizerFactory,
    unreachable_normalization_prompts,
)

setup_logging()


def setup_backend(settings: Settings):
    if settings.backend_type is BackendType.TORCH:
        import torch

        torch.set_num_threads(settings.torch.num_threads)
        torch.set_num_interop_threads(settings.torch.num_interop_threads)
        if settings.torch.flush_denormal and hasattr(torch, "set_flush_denormal"):
            torch.set_flush_denormal(True)


def create_openai_client(settings: OpenAiSettings) -> AsyncOpenAI:
    if settings is None:
        return None

    if not settings.base_url or not settings.api_key:
        return None

    openai_client = AsyncOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
    )

    return openai_client


async def register_zeroconf_server(name: str, for_server: AsyncServer):
    if not isinstance(for_server, AsyncTcpServer):
        raise ValueError("Zeroconf requires tcp:// uri")

    from wyoming.zeroconf import HomeAssistantZeroconf

    tcp_server: AsyncTcpServer = for_server
    hass_zeroconf = HomeAssistantZeroconf(
        name=name,
        port=tcp_server.port,
        host=tcp_server.host,
    )
    await hass_zeroconf.register_server()
    logger.debug("Zeroconf discovery enabled")


def warn_unreachable_prompts(settings: NormalizationSettings, data_storage: YamlDataStorage):
    """Say which configured normalization prompts can never be selected.

    Reported rather than refused: an unreachable prompt is inert, so the server still
    synthesizes, and a prompt for a Language no served Model Info declares yet is a
    staged configuration rather than a mistake. What it must not be is silent — the
    symptom otherwise is text that quietly comes back unnormalized.
    """
    unreachable = unreachable_normalization_prompts(settings, data_storage)
    for text_format, languages in unreachable.items():
        logger.warning(
            "Normalization prompts for {languages} under '{text_format}' are keyed by a "
            "Language no Model Info this instance serves declares, so they are never "
            "selected. Prompts are keyed by the Language itself, not by a locale with a "
            "region suffix.",
            languages=", ".join(sorted(languages)),
            text_format=text_format,
        )


async def main():
    settings = get_settings()
    logger.debug(settings)

    setup_backend(settings)

    server = AsyncServer.from_uri(settings.uri)

    normalization_client = create_openai_client(settings.normalization.openai)
    data_storage = YamlDataStorage(
        config_path_or_model=settings.data_yml_path, active_models=settings.active_models
    )
    warn_unreachable_prompts(settings.normalization, data_storage)
    engine_manager = TtsEngineManager(
        backendType=settings.backend_type,
        cache_half_life_seconds=settings.cache_half_life,
        cache_capacity=settings.max_models,
        inference_timeout=settings.inference_timeout,
        max_concurrent_sentences_per_model=settings.max_concurrent_sentences_per_model,
        engine_factory=TtsEngineFactory(settings=settings),
        data_storage=data_storage,
    )

    middlewares = [
        ResolveLanguageMiddleware().invoke,
        SplitSentencesMiddleware(
            max_sentence_chars=settings.max_sentence_chars,
            text_sentencizer_factory=TextSentencizerFactory(),
        ).invoke,
        NormalizeTextMiddleware(
            timeout=settings.normalization.timeout,
            max_concurrent_sentences=settings.normalization.max_concurrent_sentences_per_request,
            text_normalizer_factory=TextNormalizerFactory(
                openai_client=normalization_client,
                settings=settings.normalization,
                storage=data_storage,
            ),
        ).invoke,
    ]

    engine_hub = TtsEngineHub(
        frame_duration=settings.frame_duration,
        middlewares=middlewares,
        engine_manager=engine_manager,
        data_storage=data_storage,
    )

    logger.info(f"Starting server on {settings.uri}")

    tasks = [
        engine_manager.warmup(),
        server.run(
            partial(
                TtsEngineHubEventHandler,
                engine_hub,
                data_storage,
                settings.app_name,
                settings.streaming,
                settings.env_type == "development",
            )
        ),
    ]

    if settings.zeroconf:
        tasks.append(register_zeroconf_server(settings.zeroconf, server))

    server_task = asyncio.gather(*tasks)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, server_task.cancel)
    loop.add_signal_handler(signal.SIGTERM, server_task.cancel)

    try:
        await server_task
    except asyncio.CancelledError:
        logger.info("Server stopped")
    finally:
        await engine_manager.close()

        if normalization_client is not None:
            await normalization_client.close()

        loop.remove_signal_handler(signal.SIGINT)
        loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
