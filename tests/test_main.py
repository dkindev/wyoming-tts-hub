import unittest.mock

from openai import AsyncOpenAI

from src.config import OpenAiSettings, Settings
from src.main import create_openai_client, setup_backend


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

    def test_missing_base_url_returns_none(self):
        """Without a base_url there is nothing to point the client at."""
        assert create_openai_client(OpenAiSettings(base_url="", api_key="key")) is None

    def test_missing_api_key_returns_none(self):
        """Without an api_key the client is not constructed."""
        settings = OpenAiSettings(base_url="http://localhost:8080/v1", api_key="")

        assert create_openai_client(settings) is None

    def test_complete_settings_build_a_client(self):
        """A fully configured settings object yields an AsyncOpenAI pointed at base_url."""
        settings = OpenAiSettings(base_url="http://localhost:8080/v1", api_key="key")

        client = create_openai_client(settings)

        assert isinstance(client, AsyncOpenAI)
        assert client.base_url == "http://localhost:8080/v1/"
