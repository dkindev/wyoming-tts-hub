import json
from enum import Enum
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic.fields import FieldInfo
from pydantic_core import Url

from src.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
# The prefix and delimiter Settings reads environment variables under.
ENV_PREFIX = Settings.model_config["env_prefix"]
NESTED_DELIMITER = Settings.model_config["env_nested_delimiter"]
CONFIG_YML = REPO_ROOT / "config.yml"


def parse_env_file(path: Path) -> dict[str, str]:
    """The key/value pairs of an env template, ignoring comments and blank lines."""
    pairs = {}

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        key, _, value = line.partition("=")
        pairs[key] = value

    return pairs


def setting_path(key: str) -> list[str]:
    """The settings a key addresses, outermost first.

    `TTS_NORMALIZATION__TEXT__ENABLED` addresses the `enabled` field of the `text`
    section of the `normalization` section, which is how nested env vars are spelled.
    Field names are lower case; env keys are not, and Settings reads either.
    """
    return [name.lower() for name in key.removeprefix(ENV_PREFIX).split(NESTED_DELIMITER)]


def resolve_field(path: list[str]) -> FieldInfo | None:
    """The field a path reaches, or None when any step of it names nothing."""
    field = Settings.model_fields.get(path[0])

    for section in path[1:]:
        if field is None:
            return None

        field = getattr(field.annotation, "model_fields", {}).get(section)

    return field


def setting_value(settings: Any, path: list[str]) -> Any:
    """Read the value a path addresses, one section at a time."""
    target = settings

    for name in path[:-1]:
        target = getattr(target, name)

    return getattr(target, path[-1])


def as_readable(value: Any) -> str:
    """A setting's value as text, so it can be compared with what was written.

    Settings coerce what an env var carries: an enum, a number, a boolean and a URL
    all come back as something other than the string that was spelled in the template.
    """
    if isinstance(value, Enum):
        value = value.value
    elif isinstance(value, Url):
        value = str(value)

    return str(value).lower()


def shipped_config() -> dict[str, Any]:
    """config.yml flattened into the same key spelling an env var would use."""
    flat: dict[str, Any] = {}

    def flatten(path: list[str], value: Any) -> None:
        if isinstance(value, dict):
            for name, nested in value.items():
                flatten([*path, name], nested)
        else:
            flat[f"{ENV_PREFIX}{NESTED_DELIMITER.join(path)}".upper()] = value

    flatten([], yaml.safe_load(CONFIG_YML.read_text()) or {})

    return flat


def env_pairs() -> dict[str, str]:
    return parse_env_file(ENV_EXAMPLE)


class TestEveryKeyResolves:
    def test_the_template_documents_the_settings_it_exists_to_document(self):
        """Guard against the checks below passing because the file is empty."""
        assert len(env_pairs()) > 20

    def test_no_setting_is_documented_twice(self):
        """A key spelled twice has one winner and one lie.

        Reading the file into a dictionary drops the earlier of the two, so a duplicate
        would otherwise pass every other check here while a reader of the file believed
        both values were in effect.
        """
        keys = [
            line.split("=", 1)[0]
            for line in ENV_EXAMPLE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        duplicated = {key for key in keys if keys.count(key) > 1}

        assert not duplicated, f"documented more than once: {sorted(duplicated)}"

    @pytest.mark.parametrize("key", sorted(env_pairs()))
    def test_every_key_names_a_setting_the_server_reads(self, key):
        """A key naming nothing is silently ignored, which is the drift this prevents."""
        assert key.startswith(ENV_PREFIX), f"{key} does not carry the {ENV_PREFIX} prefix"
        assert resolve_field(setting_path(key)) is not None, f"{key} is read by nothing"


class TestEveryValueIsAccepted:
    @pytest.mark.parametrize("key", sorted(env_pairs()))
    def test_the_setting_takes_the_value_the_template_gives_it(self, key, monkeypatch):
        """The template must not ship a value its own setting would reject or reshape."""
        monkeypatch.setenv(key, env_pairs()[key])

        path = setting_path(key)
        value = setting_value(Settings(_env_file=None), path)

        if isinstance(value, list):
            # A list arrives as JSON in an env var, so it is compared once parsed.
            assert json.loads(env_pairs()[key]) == value, f"{key} was read as {value!r}"

            return

        if isinstance(value, int | float) and not isinstance(value, bool):
            # A number is compared as a number: 50 and 50.0 are the same setting value.
            assert float(value) == float(
                env_pairs()[key]
            ), f"{key} was read as {value!r}, not the {env_pairs()[key]!r} the template ships"

            return

        assert (
            as_readable(value) == env_pairs()[key].strip().lower()
        ), f"{key} was read as {value!r}, not the {env_pairs()[key]!r} the template ships"

    def test_a_nested_key_reaches_the_section_it_names(self, monkeypatch):
        """A Text Format level is part of the key, so normalization keys are nested."""
        monkeypatch.setenv("TTS_NORMALIZATION__SSML__ENABLED", "true")

        settings = Settings(_env_file=None)

        assert settings.normalization.ssml.enabled is True


class TestValuesMatchTheShippedConfiguration:
    def test_the_two_sources_of_truth_are_comparable(self):
        """Guard against the comparison below passing by matching nothing."""
        assert len(set(env_pairs()) & set(shipped_config())) > 20

    @pytest.mark.parametrize("key", sorted(set(env_pairs()) & set(shipped_config())))
    def test_a_value_is_the_one_config_ships(self, key):
        """Env vars outrank config.yml, so the template must not change a shipped value."""
        from_env = env_pairs()[key]
        from_config = shipped_config()[key]

        if isinstance(from_config, list):
            # A list is spelled as JSON in an env var and as YAML in config.yml, so the
            # two are compared once parsed rather than as text.
            assert (
                json.loads(from_env) == from_config
            ), f"{key} is {from_env!r} in .env.example but {from_config!r} in config.yml"
            return

        assert (
            from_env.lower() == str(from_config).lower()
        ), f"{key} is {from_env!r} in .env.example but {from_config!r} in config.yml"
