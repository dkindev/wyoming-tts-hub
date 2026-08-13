import pytest

from src.config import Settings
from src.main import create_storage
from tests.helpers import make_merged_yaml


@pytest.fixture
def data_config(tmp_path):
    """Return a path to a data.yml declaring two models with voices."""
    return make_merged_yaml(
        tmp_path,
        {
            "v5_5_ru": {
                "engine_type": "silero",
                "languages": ["ru"],
                "voices": [{"name": "aidar"}],
            },
            "v3_en": {
                "engine_type": "silero",
                "languages": ["en"],
                "voices": [{"name": "en_0", "speaker": "en_2"}],
            },
        },
    )


class TestCreateStorage:
    def test_unknown_active_model_fails_boot_naming_ids(self, monkeypatch, data_config):
        """create_storage fails at boot when active_models references an unknown model id."""
        monkeypatch.setenv("TTS_DATA_YML_PATH", data_config)
        monkeypatch.setenv("TTS_ACTIVE_MODELS", '["unknown_model"]')

        with pytest.raises(ValueError, match="unknown_model"):
            create_storage(Settings())

    def test_active_models_filter_applied(self, monkeypatch, data_config):
        """create_storage serves only models listed in active_models."""
        monkeypatch.setenv("TTS_DATA_YML_PATH", data_config)
        monkeypatch.setenv("TTS_ACTIVE_MODELS", '["v5_5_ru"]')

        storage = create_storage(Settings())

        assert storage.get_model("v5_5_ru") is not None
        assert storage.get_model("v3_en") is None
        assert not any(v.model_id == "v3_en" for v in storage.get_voices())
