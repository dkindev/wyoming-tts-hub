import os
import unittest.mock

import pytest
import torch

from src.config import NormalizationSettings, Settings

# ---------------------------------------------------------------------------
# Fixtures — shared by all test files
# ---------------------------------------------------------------------------

# The prefix Settings reads the process environment under, taken from the setting
# itself so a change to it cannot silently reopen the leak.
SERVER_ENV_PREFIX = Settings.model_config["env_prefix"]

# OpenAiSettings falls back to these unprefixed names, so they are leaks too.
STANDARD_OPENAI_ENV_VARS = ("OPENAI_API_KEY", "OPENAI_BASE_URL")


@pytest.fixture(autouse=True)
def hermetic_environment(tmp_path, monkeypatch):
    """Run every test with only the server environment it sets up for itself.

    Settings are assembled from several sources at once: the process environment, a
    local `.env` file, and a YAML config file. The last two are resolved relative to
    the working directory, so a test that does not control them sees whatever the
    machine it runs on has configured — which is how the suite ends up green in CI
    and red on a configured workstation.

    This clears the prefixed environment, points the YAML source at a per-test file,
    and runs from that same per-test directory so no file of the developer's checkout
    is an input. A test that wants a setting from the environment still sets it,
    after this fixture runs.

    The per-test config carries only an `active_models` allowlist, so the default
    settings serve one model rather than nothing. A test that exercises the YAML
    source points `--config` at its own file and therefore ignores this one.

    The dotenv source is switched off outright rather than merely outvoted: outvoting
    it means every test has to set whatever it expects to win, which is how a local
    `.env` file ends up deciding what the suite asserts.
    """
    for name in [*os.environ, *STANDARD_OPENAI_ENV_VARS]:
        if name.startswith(SERVER_ENV_PREFIX) or name in STANDARD_OPENAI_ENV_VARS:
            monkeypatch.delenv(name, raising=False)

    monkeypatch.setitem(Settings.model_config, "env_file", None)

    config_path = tmp_path / "config.yml"
    config_path.write_text("active_models: [test_model]\n")

    monkeypatch.setenv(f"{SERVER_ENV_PREFIX}CONFIG_PATH", str(config_path))
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def mock_model():
    """Return a MagicMock Silero model with symbols and apply_tts."""
    mock_audio = torch.zeros(1, 48000)
    m = unittest.mock.MagicMock()
    m.symbols = "_.!,-:;?abcdefghijklmnopqrstuvwxyz "
    m.apply_tts.return_value = mock_audio
    return m


@pytest.fixture
def mock_importer(mock_model):
    """Return a MagicMock PackageImporter that returns mock_model."""
    imp = unittest.mock.MagicMock()
    imp.load_pickle.return_value = mock_model
    return imp


@pytest.fixture
def default_normalization_settings():
    """Return NormalizationSettings with all defaults."""
    return NormalizationSettings()


@pytest.fixture
def mock_openai_client():
    """AsyncMock(spec=AsyncOpenAI) with chat.completions.create returning a fake response."""
    from openai import AsyncOpenAI

    client = unittest.mock.AsyncMock(spec=AsyncOpenAI)
    response = unittest.mock.MagicMock()
    response.choices = [
        unittest.mock.MagicMock(message=unittest.mock.MagicMock(content="normalized text"))
    ]
    client.chat.completions.create = unittest.mock.AsyncMock(return_value=response)
    return client


@pytest.fixture
def mock_storage():
    """Mock DataStorage returning None for all normalization lookups."""
    storage = unittest.mock.MagicMock()
    storage.get_voice_normalization.return_value = None
    storage.get_prompt.return_value = None
    return storage
