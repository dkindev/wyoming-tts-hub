import os
from pathlib import Path

import pytest
import yaml
from pydantic_settings import YamlConfigSettingsSource

from src.config import Settings
from src.tts.models import BackendType


def write_config(tmp_path, body, name="other-config.yml"):
    """Write a config file body and return its path, for a test to point Settings at."""
    config_path = tmp_path / name
    config_path.write_text(body)
    return str(config_path)


class TestTtsStreaming:
    def test_default_is_true(self):
        """streaming defaults to True (enabled)."""
        settings = Settings()
        assert settings.streaming is True

    def test_env_var_disables_streaming(self, monkeypatch):
        """TTS_STREAMING=false sets streaming to False."""
        monkeypatch.setenv("TTS_STREAMING", "false")
        settings = Settings()
        assert settings.streaming is False

    def test_cli_flag_no_streaming_disables(self, monkeypatch):
        """--no-streaming CLI flag sets streaming to False."""
        monkeypatch.setattr("sys.argv", ["prog", "--no-streaming"])
        settings = Settings()
        assert settings.streaming is False

    def test_cli_flag_streaming_enables(self, monkeypatch):
        """--streaming CLI flag sets streaming to True."""
        monkeypatch.setattr("sys.argv", ["prog", "--streaming"])
        settings = Settings()
        assert settings.streaming is True


class TestTtsUri:
    def test_default_uri(self):
        """uri defaults to tcp://127.0.0.1:10200."""
        settings = Settings()
        assert settings.uri == "tcp://127.0.0.1:10200"

    def test_uri_from_env_var(self, monkeypatch):
        """uri is overridable via TTS_URI environment variable."""
        monkeypatch.setenv("TTS_URI", "tcp://0.0.0.0:10201")
        settings = Settings()
        assert settings.uri == "tcp://0.0.0.0:10201"


class TestTtsZeroconf:
    def test_zeroconf_defaults_to_wyoming_tts_hub(self):
        """zeroconf defaults to 'wyoming-tts-hub' (enabled)."""
        settings = Settings()
        assert settings.zeroconf == "wyoming-tts-hub"

    def test_zeroconf_silero_is_truthy(self):
        """Non-empty zeroconf evaluates as truthy (enabled)."""
        settings = Settings()
        assert settings.zeroconf

    def test_zeroconf_from_env_var(self, monkeypatch):
        """zeroconf is overridable via TTS_ZEROCONF environment variable."""
        monkeypatch.setenv("TTS_ZEROCONF", "my_tts")
        settings = Settings()
        assert settings.zeroconf == "my_tts"


class TestSileroSettings:
    def test_silero_settings_defaults(self):
        """SileroSettings has expected defaults."""
        settings = Settings()
        assert settings.silero.sample_rate == 48000
        assert (
            str(settings.silero.models_yml_url)
            == "https://raw.githubusercontent.com/snakers4/silero-models/refs/heads/master/models.yml"
        )
        assert settings.silero.models_yml_hash == ""

    def test_silero_sample_rate_env_var(self, monkeypatch):
        """TTS_SILERO__SAMPLE_RATE overrides sample_rate."""
        monkeypatch.setenv("TTS_SILERO__SAMPLE_RATE", "24000")
        settings = Settings()
        assert settings.silero.sample_rate == 24000

    def test_silero_sample_rate_coerces_from_string(self, monkeypatch):
        """sample_rate is coerced from string to int."""
        monkeypatch.setenv("TTS_SILERO__SAMPLE_RATE", "16000")
        settings = Settings()
        assert settings.silero.sample_rate == 16000

    def test_silero_models_yml_hash_invalid_raises(self, monkeypatch):
        """Invalid models_yml_hash raises ValueError."""
        monkeypatch.setenv("TTS_SILERO__MODELS_YML_HASH", "not-a-valid-hash")
        with pytest.raises(ValueError, match="64-character hex string"):
            Settings()

    def test_silero_models_yml_hash_empty_is_valid(self):
        """Empty models_yml_hash is valid."""
        settings = Settings()
        assert settings.silero.models_yml_hash == ""

    def test_silero_models_yml_hash_none_is_valid(self, monkeypatch):
        """models_yml_hash blanked is treated as empty."""
        monkeypatch.setenv("TTS_SILERO__MODELS_YML_HASH", "   ")
        settings = Settings()
        assert settings.silero.models_yml_hash == ""

    def test_models_dir_env_var(self, monkeypatch):
        """TTS_MODELS_DIR overrides models_dir."""
        monkeypatch.setenv("TTS_MODELS_DIR", "/custom/models")
        settings = Settings()
        assert settings.models_dir == "/custom/models"

    def test_models_dir_comes_from_the_yaml_source(self, monkeypatch, tmp_path):
        """models_dir in the config file wins over the Python default."""
        cfg = write_config(tmp_path, "active_models: [a]\nmodels_dir: models\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", cfg])

        settings = Settings()

        assert settings.models_dir == "models"

    def test_models_dir_falls_back_to_the_python_default(self):
        """With no config file setting it, models_dir is the Python default.

        Asserted as a literal rather than read from the shipped config.yml, so the
        default cannot be "fixed" by changing the file and left contradicting it.
        """
        settings = Settings()
        assert settings.models_dir == "models"


class TestActiveModels:
    def test_missing_active_models_serves_nothing(self, monkeypatch, tmp_path):
        """A config without active_models starts with an empty allowlist."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("models_dir: models\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().active_models == []

    def test_empty_active_models_is_allowed(self, monkeypatch, tmp_path):
        """An empty active_models list is read as an empty allowlist, not a validation error."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("active_models: []\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().active_models == []

    def test_null_active_models_serves_nothing(self, monkeypatch, tmp_path):
        """An explicit null is read as an empty allowlist."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("active_models: null\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().active_models == []

    def test_yaml_list_populates_active_models(self, monkeypatch, tmp_path):
        """active_models: [a, b] in YAML populates the setting."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("active_models: [a, b]\n")
        monkeypatch.delenv("TTS_ACTIVE_MODELS", raising=False)
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        settings = Settings()
        assert settings.active_models == ["a", "b"]

    def test_cli_repeated_flags_populate_active_models(self, monkeypatch):
        """Repeated --active_models CLI flags populate the setting as a list."""
        monkeypatch.setattr(
            "sys.argv",
            ["prog", "--active_models", "a", "--active_models", "b"],
        )

        settings = Settings()
        assert settings.active_models == ["a", "b"]

    def test_env_json_populates_active_models(self, monkeypatch):
        """TTS_ACTIVE_MODELS as a JSON array populates the setting."""
        monkeypatch.setenv("TTS_ACTIVE_MODELS", '["a", "b"]')

        settings = Settings()
        assert settings.active_models == ["a", "b"]


class TestWarmupModels:
    def test_missing_warmup_models_is_empty(self, monkeypatch, tmp_path):
        """A config without warmup_models starts with no model to pre-warm."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("models_dir: models\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().warmup_models == []

    def test_empty_warmup_models_is_allowed(self, monkeypatch, tmp_path):
        """An empty warmup_models list is read as no model to pre-warm."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("warmup_models: []\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().warmup_models == []

    def test_null_warmup_models_is_empty(self, monkeypatch, tmp_path):
        """An explicit null is read as no model to pre-warm."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("warmup_models: null\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().warmup_models == []

    def test_yaml_list_populates_warmup_models(self, monkeypatch, tmp_path):
        """warmup_models: [a, b] in YAML populates the setting."""
        cfg = tmp_path / "config.yml"
        cfg.write_text("warmup_models: [a, b]\n")
        monkeypatch.delenv("TTS_WARMUP_MODELS", raising=False)
        monkeypatch.setattr("sys.argv", ["prog", "--config", str(cfg)])

        assert Settings().warmup_models == ["a", "b"]

    def test_cli_repeated_flags_populate_warmup_models(self, monkeypatch):
        """Repeated --warmup_models CLI flags populate the setting as a list."""
        monkeypatch.setattr(
            "sys.argv",
            ["prog", "--warmup_models", "a", "--warmup_models", "b"],
        )

        assert Settings().warmup_models == ["a", "b"]

    def test_env_json_populates_warmup_models(self, monkeypatch):
        """TTS_WARMUP_MODELS as a JSON array populates the setting."""
        monkeypatch.setenv("TTS_WARMUP_MODELS", '["a", "b"]')

        assert Settings().warmup_models == ["a", "b"]


class TestBackendType:
    def test_default_is_torch(self):
        """backend_type defaults to BackendType.TORCH."""
        settings = Settings()
        assert settings.backend_type == BackendType.TORCH

    def test_env_var_populates(self, monkeypatch):
        """TTS_BACKEND_TYPE=torch sets backend_type to TORCH."""
        monkeypatch.setenv("TTS_BACKEND_TYPE", "torch")
        settings = Settings()
        assert settings.backend_type == BackendType.TORCH

    def test_yaml_populates(self, monkeypatch, tmp_path):
        """backend_type: torch in YAML populates the setting."""
        cfg = write_config(
            tmp_path, "backend_type: torch\nactive_models: [v5_6_ru]\n", name="config.yml"
        )
        monkeypatch.setattr("sys.argv", ["prog", "--config", cfg])

        settings = Settings()
        assert settings.backend_type == BackendType.TORCH

    def test_cli_flag_populates(self, monkeypatch):
        """--backend_type torch CLI flag populates the setting."""
        monkeypatch.setattr("sys.argv", ["prog", "--backend_type", "torch"])

        settings = Settings()
        assert settings.backend_type == BackendType.TORCH


class TestTorchSettings:
    def test_device_defaults_to_cpu(self):
        """device defaults to 'cpu' when no source sets it."""
        settings = Settings()
        assert settings.torch.device == "cpu"

    def test_device_from_env_var(self, monkeypatch):
        """TTS_TORCH__DEVICE overrides the compute device."""
        monkeypatch.setenv("TTS_TORCH__DEVICE", "cuda")
        settings = Settings()
        assert settings.torch.device == "cuda"

    def test_device_from_the_config_file(self, monkeypatch, tmp_path):
        """device in the config file overrides the Python default."""
        cfg = write_config(tmp_path, "active_models: [a]\ntorch:\n  device: cuda\n")
        monkeypatch.setattr("sys.argv", ["prog", "--config", cfg])

        settings = Settings()

        assert settings.torch.device == "cuda"


class TestYamlConfigSource:
    def test_config_yml_overrides_defaults(self, monkeypatch, tmp_path):
        """Values in the config file take priority over the Field defaults."""
        cfg = write_config(
            tmp_path,
            "active_models: [a]\n"
            "env_type: production\n"
            "uri: tcp://0.0.0.0:10201\n"
            "max_models: 5\n"
            "torch:\n  num_threads: 8\n"
            "silero:\n  sample_rate: 24000\n",
        )
        monkeypatch.setattr("sys.argv", ["prog", "--config", cfg])

        settings = Settings()

        assert settings.env_type == "production"
        assert settings.uri == "tcp://0.0.0.0:10201"
        assert settings.torch.num_threads == 8
        assert settings.silero.sample_rate == 24000
        assert settings.max_models == 5

    def test_yaml_source_is_in_priority_chain(self):
        """YamlConfigSettingsSource is present in the priority chain."""
        sources = Settings.settings_customise_sources(Settings, None, None, None, None)
        assert any(
            issubclass(s, YamlConfigSettingsSource)
            if isinstance(s, type)
            else isinstance(s, YamlConfigSettingsSource)
            for s in sources
        )


class TestHermeticConstruction:
    """Settings see only what the test set up, whatever the machine has configured."""

    def test_checked_in_config_file_is_not_read(self):
        """The repository's config.yml does not reach a test.

        That file sets env_type to production; a test that reads only its own
        sources gets the Field default instead.
        """
        settings = Settings()

        assert settings.env_type == "development"

    def test_local_env_file_is_not_read(self):
        """A .env file beside the test does not reach it."""
        local_env = Path(".env")
        local_env.write_text("TTS_MODELS_DIR=/from/local/env\nTTS_ACTIVE_MODELS=['local']\n")

        settings = Settings()

        assert settings.models_dir == "models"
        assert settings.active_models == ["test_model"]

    def test_the_shipped_config_agrees_with_the_default(self):
        """The file and the default name one directory, so neither can drift alone.

        The documented Docker run command mounts this directory, so an operator who
        deletes the line from their own configuration lands on the layout the docs
        describe rather than a second, undocumented one.
        """
        shipped = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / "config.yml").read_text()
        )

        assert shipped["models_dir"] == Settings.model_fields["models_dir"].default

    def test_config_path_environment_variable_selects_the_config_file(self, monkeypatch, tmp_path):
        """TTS_CONFIG_PATH decides which YAML file the source reads."""
        cfg = write_config(
            tmp_path,
            "active_models: [elsewhere]\nmodels_dir: /from/config/path\n",
            name="elsewhere.yml",
        )
        monkeypatch.setenv("TTS_CONFIG_PATH", cfg)

        settings = Settings()

        assert settings.models_dir == "/from/config/path"
        assert settings.active_models == ["elsewhere"]

    def test_a_test_can_still_override_through_the_environment(self, monkeypatch):
        """The environment remains a way to set a setting when a test means to."""
        monkeypatch.setenv("TTS_MODELS_DIR", "/set/by/test")

        settings = Settings()

        assert settings.models_dir == "/set/by/test"

    def test_standard_openai_environment_does_not_leak(self):
        """The unprefixed OpenAI variables Settings falls back to are cleared too."""
        assert os.environ.get("OPENAI_API_KEY") is None
        assert Settings().normalization.openai.api_key == ""


class TestShippedNormalizationPrompts:
    """The prompts the project ships are keyed the way the server looks them up."""

    @staticmethod
    def shipped():
        """The settings and the data file, as the server ships them."""
        root = Path(__file__).resolve().parent.parent
        config = yaml.safe_load((root / "config.yml").read_text())
        data = yaml.safe_load((root / "data" / "data.yml").read_text())
        return config, data

    @staticmethod
    def prompt_keys(config) -> set[str]:
        """Every Language a server-wide prompt is keyed by, across both Text Formats."""
        return {
            language
            for text_format in ("text", "ssml")
            for language in (config["normalization"][text_format].get("prompts") or {})
        }

    def test_the_shipped_file_prompts_something(self):
        """Guard against the checks below passing because no prompt is written."""
        config, _ = self.shipped()

        assert self.prompt_keys(config)

    def test_every_prompt_is_keyed_by_a_declared_language(self):
        """A prompt keyed by a locale is unreachable and fails silently.

        The Language a request resolves to is one a Model Info declares, and a locale
        form is refused as a request Language, so a prompt stored under one can never
        be selected.
        """
        config, data = self.shipped()
        declared = {
            language for model in data["models"].values() for language in model["languages"]
        }

        unreachable = self.prompt_keys(config) - declared

        assert not unreachable, f"keyed by a Language no Model Info declares: {sorted(unreachable)}"

    def test_a_prompt_names_a_language_and_a_model(self):
        config, _ = self.shipped()

        for text_format in ("text", "ssml"):
            for language, prompt in (
                config["normalization"][text_format].get("prompts") or {}
            ).items():
                assert prompt["text"], f"{language}/{text_format} has no prompt text"
                assert prompt["model"], f"{language}/{text_format} names no LLM model"


def test_env_example_carries_no_prompt_keys():
    """Server-wide prompts live only in the config file, so the template omits them.

    The two files are both read at runtime and are held to each other by
    `test_env_example.py`; a prompt key added to the template would claim an
    environment variable that nothing reads.
    """
    template = (Path(__file__).resolve().parent.parent / ".env.example").read_text()

    assert "PROMPTS" not in template.upper()
