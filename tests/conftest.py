import unittest.mock

import pytest
import torch

from src.config import NormalizationSettings

# ---------------------------------------------------------------------------
# Fixtures — shared by all test files
# ---------------------------------------------------------------------------


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
