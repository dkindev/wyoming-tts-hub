import unittest.mock

import pytest
from openai import AsyncOpenAI

from src.config import (
    NormalizationPrompt,
    NormalizationSettings,
    OpenAiSettings,
    Settings,
    TextFormatNormalizationSettings,
)
from src.main import create_openai_client, setup_backend, warn_unreachable_prompts
from tests.helpers import FakeDataStorage, make_model_info


@pytest.fixture
def usable_settings():
    """OpenAiSettings complete enough for create_openai_client to build a client."""
    return OpenAiSettings(base_url="http://localhost:8080/v1", api_key="key")


class TestSetupBackend:
    def test_torch_backend_applies_thread_settings(self, monkeypatch):
        """The torch backend pushes the configured thread counts into torch."""
        monkeypatch.setenv("TTS_TORCH__NUM_THREADS", "3")
        monkeypatch.setenv("TTS_TORCH__NUM_INTEROP_THREADS", "2")
        monkeypatch.setenv("TTS_TORCH__FLUSH_DENORMAL", "false")
        settings = Settings()

        with (
            unittest.mock.patch("torch.set_num_threads") as set_num_threads,
            unittest.mock.patch("torch.set_num_interop_threads") as set_interop,
            unittest.mock.patch("torch.set_flush_denormal") as flush_denormal,
        ):
            setup_backend(settings)

        set_num_threads.assert_called_once_with(3)
        set_interop.assert_called_once_with(2)
        flush_denormal.assert_not_called()

    def test_torch_backend_applies_flush_denormal_when_enabled(self, monkeypatch):
        """flush_denormal is only pushed when the setting asks for it."""
        monkeypatch.setenv("TTS_TORCH__FLUSH_DENORMAL", "true")
        settings = Settings()

        with (
            unittest.mock.patch("torch.set_num_threads"),
            unittest.mock.patch("torch.set_num_interop_threads"),
            unittest.mock.patch("torch.set_flush_denormal") as flush_denormal,
        ):
            setup_backend(settings)

        flush_denormal.assert_called_once_with(True)


class TestCreateOpenAiClient:
    def test_no_settings_returns_none(self):
        """Absent normalization settings mean no client."""
        assert create_openai_client(None) is None

    def test_missing_base_url_returns_none(self, usable_settings):
        """Without a base_url there is nothing to point the client at."""
        settings = usable_settings.model_copy(update={"base_url": ""})

        assert create_openai_client(settings) is None

    def test_missing_api_key_returns_none(self, usable_settings):
        """Without an api_key the client is not constructed."""
        settings = usable_settings.model_copy(update={"api_key": ""})

        assert create_openai_client(settings) is None

    def test_complete_settings_build_a_client(self, usable_settings):
        """A fully configured settings object yields an AsyncOpenAI pointed at base_url."""
        client = create_openai_client(usable_settings)

        assert isinstance(client, AsyncOpenAI)
        assert client.base_url == f"{usable_settings.base_url}/"


class TestWarnUnreachablePrompts:
    """An unreachable prompt is reported at startup, and never blocks the server."""

    def storage(self, *languages):
        return FakeDataStorage(models=[make_model_info(languages=list(languages))])

    def test_an_unreachable_prompt_is_reported(self):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru_RU": NormalizationPrompt(text="t", model="m")}
            )
        )

        with unittest.mock.patch("src.main.logger.warning") as warning:
            warn_unreachable_prompts(settings, self.storage("ru"))

        warning.assert_called_once()
        assert "ru_RU" in warning.call_args.kwargs["languages"]

    def test_a_reachable_prompt_is_not_reported(self):
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru": NormalizationPrompt(text="t", model="m")}
            )
        )

        with unittest.mock.patch("src.main.logger.warning") as warning:
            warn_unreachable_prompts(settings, self.storage("ru"))

        warning.assert_not_called()

    def test_reporting_does_not_raise(self):
        """The server starts either way: an inert prompt is not a startup failure."""
        settings = NormalizationSettings(
            text=TextFormatNormalizationSettings(
                prompts={"ru_RU": NormalizationPrompt(text="t", model="m")}
            )
        )

        assert warn_unreachable_prompts(settings, self.storage("ru")) is None
