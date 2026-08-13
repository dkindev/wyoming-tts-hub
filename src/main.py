import asyncio
import signal
from functools import partial

import torch
from loguru import logger
from openai import AsyncOpenAI
from wyoming.server import AsyncServer, AsyncTcpServer

from src.config import Settings, get_settings
from src.handler import SileroEventHandler
from src.logger import setup_logging
from src.tts.data_storage import DataStorage, YamlDataStorage
from src.tts.engine import SileroTTSEngine
from src.tts.models import TTSConfig
from src.tts.preprocessing import TextNormalizerFactory, TextSentenizerFactory

setup_logging()


def create_storage(settings: Settings) -> DataStorage:
    return YamlDataStorage(settings.data_yml_path, active_models=settings.active_models)


def create_text_sentenizer_factory() -> TextSentenizerFactory:
    return TextSentenizerFactory()


def create_text_normalizer_factory(
    openai_client: AsyncOpenAI, settings: Settings, storage: DataStorage
) -> TextNormalizerFactory:
    return TextNormalizerFactory(
        openai_client=openai_client,
        settings=settings.normalization,
        storage=storage,
    )


def create_engine(
    settings: Settings,
    storage: DataStorage,
    text_sentenizer_factory: TextSentenizerFactory,
    text_normalizer_factory: TextNormalizerFactory,
) -> SileroTTSEngine:
    torch.set_num_threads(settings.torch.num_threads)
    torch.set_num_interop_threads(settings.torch.num_interop_threads)
    if settings.torch.flush_denormal and hasattr(torch, "set_flush_denormal"):
        torch.set_flush_denormal(True)

    config = TTSConfig(
        device=settings.torch.device,
        inference_timeout=settings.inference_timeout,
        frame_duration=settings.frame_duration,
        sample_rate=settings.silero.sample_rate,
        max_models=settings.max_models,
        cache_half_life=settings.cache_half_life,
        max_concurrent_sentences_per_model=settings.max_concurrent_sentences_per_model,
        max_sentence_chars=settings.max_sentence_chars,
        models_dir=settings.models_dir,
        models_yml_url=settings.silero.models_yml_url,
        models_yml_hash=settings.silero.models_yml_hash,
    )

    return SileroTTSEngine(
        config=config,
        storage=storage,
        text_sentenizer_factory=text_sentenizer_factory,
        text_normalizer_factory=text_normalizer_factory,
    )


def create_openai_client(settings: Settings) -> AsyncOpenAI:
    config = settings.openai
    if config is None:
        return None

    if not config.base_url or not config.api_key:
        return None

    openai_client = AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
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


async def main():
    settings = get_settings()
    logger.debug(settings)

    server = AsyncServer.from_uri(settings.uri)

    openai_client = create_openai_client(settings)

    storage = create_storage(settings)
    text_sentenizer_factory = create_text_sentenizer_factory()
    text_normalizer_factory = create_text_normalizer_factory(openai_client, settings, storage)
    engine = create_engine(settings, storage, text_sentenizer_factory, text_normalizer_factory)

    logger.info(f"Starting server on {settings.uri}")

    tasks = [
        engine.warmup(),
        server.run(
            partial(
                SileroEventHandler,
                engine,
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
        await engine.shutdown()

        if openai_client is not None:
            await openai_client.close()

        loop.remove_signal_handler(signal.SIGINT)
        loop.remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
