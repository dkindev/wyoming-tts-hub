import unittest.mock

import pytest
import torch

from src.config import NormalizationSettings
from src.tts.models import NormalizationOptions, TtsConfig

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
def default_tts_config():
    """Return a TTSConfig with sensible defaults for testing."""
    return TtsConfig(
        device="cpu",
        inference_timeout=5,
        frame_duration=50,
        sample_rate=48000,
        max_models=2,
        cache_half_life=60,
        max_concurrent_sentences_per_model=2,
        max_sentence_chars=48000,
        models_dir=".models/silero",
        models_yml_url="https://example.com/models.yml",
        models_yml_hash="",
    )


@pytest.fixture
def mock_package_importer(mock_importer):
    """Patch torch.package.PackageImporter to return mock_importer."""
    with unittest.mock.patch(
        "src.tts.engine.torch.package.PackageImporter",
        return_value=mock_importer,
    ):
        yield


@pytest.fixture
def normalization_options(mock_model):
    """Return NormalizationOptions with a voice, model, and silero model."""
    from tests.helpers import make_model, make_voice

    return NormalizationOptions(
        voice=make_voice(voice_id="test-voice", name="Test Voice"),
        model=make_model(),
        silero_model=mock_model,
    )


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
    """Mock SileroTTSConfigStorage returning None for all lookups."""
    storage = unittest.mock.MagicMock()
    storage.get_voice_normalization.return_value = None
    storage.get_prompt.return_value = None
    return storage
