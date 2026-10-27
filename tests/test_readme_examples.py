import re
from pathlib import Path

import pytest
import yaml

from src.tts.data_storage import YamlDataStorage
from src.tts.models import EngineType, ModelInfo, NormalizationType, TextFormat, Voice

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
DOCKERFILE = REPO_ROOT / "Dockerfile"
DATA_YML = REPO_ROOT / "data" / "data.yml"
CONFIG_YML = REPO_ROOT / "config.yml"

QWEN_BASE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
QWEN_CUSTOM_VOICE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"

MODELS_DIR = "models"
"""The directory the server caches models under, as the documentation names it."""

PROJECT_NAME = "wyoming-tts-hub"
"""The distribution, command and image tag, which the documentation must agree with."""

PROJECT_URL = f"https://github.com/dkindev/{PROJECT_NAME}"
"""Where the project lives, as the README documents it."""

COMMAND = PROJECT_NAME
"""The console script, which the distribution installs under its own name."""

IMAGE_TAG = PROJECT_NAME
"""The Docker image tag the README documents building and running."""

IMAGE_WORKDIR = "/app"
"""The directory the image runs in, which relative paths resolve against."""

# The form a Voice's id takes: the Model Info's id, then the Voice's name.
VOICE_ID_FORM = "<model id>-<voice name>"


def yaml_examples(text: str) -> list[str]:
    """Every fenced yaml block in a document, in the order they appear."""
    return [block.strip() for block in re.findall(r"```yaml\n(.*?)```", text, re.DOTALL)]


def documented_fields(heading: str) -> set[str]:
    """The field names in the first column of the table under a heading.

    Tables are half the documentation surface an example cannot cover, so the names
    they claim are checked against the shapes the code has.
    """
    section = README.read_text().split(f"### {heading}", 1)[1].split("\n###", 1)[0]
    fields = set()

    for line in section.splitlines():
        if not line.startswith("| `"):
            continue

        name = line.split("|")[1].strip().strip("`")
        if name and name != "Field":
            fields.add(name)

    return fields


def main_models_example() -> str:
    """The example introducing models and their voices, as opposed to a later override."""
    return next(e for e in yaml_examples(README.read_text()) if "voices" in e)


def normalization_example() -> str:
    return next(e for e in yaml_examples(README.read_text()) if "normalization" in e)


def qwen_models_example() -> str:
    """The example showing both Qwen3-TTS checkpoint families."""
    return next(e for e in yaml_examples(README.read_text()) if "engine_type: qwen3" in e)


def load_example(tmp_path: Path, example: str, index: int) -> YamlDataStorage:
    """Load a documented example the way the server loads the data file."""
    written = yaml.safe_load(example)
    model_ids = list(written.get("models", {}))

    path = tmp_path / f"readme-example-{index}.yml"
    path.write_text(example)

    return YamlDataStorage(config_path_or_model=path, active_models=model_ids)


def shipped_active_models() -> list[str]:
    """The model ids the shipped config actually activates."""
    return list(yaml.safe_load(CONFIG_YML.read_text())["active_models"])


def declared_model_ids() -> list[str]:
    """Every model id the shipped data file declares."""
    return list(yaml.safe_load(DATA_YML.read_text())["models"])


class TestEveryExampleLoads:
    def test_the_readme_documents_at_least_one_model_and_voice(self):
        """Guard against the checks below passing because no example was found."""
        assert len(yaml_examples(README.read_text())) >= 2

    @pytest.mark.parametrize("index", range(len(yaml_examples(README.read_text()))))
    def test_an_example_written_as_shown_loads(self, tmp_path, index):
        """An example the reader copies must survive being read as written.

        A shape the server does not read is dropped in silence, so the only way a reader
        finds out is by getting audio that does not match what they wrote.
        """
        example = yaml_examples(README.read_text())[index]

        storage = load_example(tmp_path, example, index)

        assert storage.get_voices() or not yaml.safe_load(example).get(
            "models"
        ), "the example wrote models, so it should yield the voices of them"


class TestWhatTheExamplesDeclare:
    def test_the_models_and_voices_come_back_as_written(self, tmp_path):
        """Every model and voice in the main example is served under the id the code derives."""
        example = main_models_example()
        written = yaml.safe_load(example).get("models", {})
        storage = load_example(tmp_path, example, 0)

        for model_id, model_data in written.items():
            model_info = storage.get_model_info(model_id)
            assert model_info is not None, f"{model_id} was not served at all"
            assert model_info.languages == model_data["languages"]

            for voice_data in model_data.get("voices", []):
                voice = storage.get_voice(f"{model_id}-{voice_data['name']}")
                assert voice is not None, f"{model_id}-{voice_data['name']} was dropped"
                assert voice.name == voice_data["name"]

    def test_a_voice_id_is_the_model_id_and_the_voice_name(self, tmp_path):
        """The id a reader is told to expect is the one the code derives."""
        storage = load_example(tmp_path, main_models_example(), 0)

        for voice in storage.get_voices():
            assert voice.id == f"{voice.model_id}-{voice.name}"

    def test_the_documented_id_form_is_the_one_derived(self):
        """The prose must state the same form the code builds, or the reader is misled."""
        assert f"`{VOICE_ID_FORM}`" in README.read_text()
        assert "ru_RU-v5_6_ru-aidar" not in README.read_text()

    def test_a_voice_normalization_example_is_read_as_written(self, tmp_path):
        """An override is read for the Voice, Language and Text Format it names."""
        example = normalization_example()
        written = yaml.safe_load(example)["models"]["v5_6_ru"]["voices"][0]["normalization"]
        storage = load_example(tmp_path, example, 1)

        for language, formats in written.items():
            for text_format, declared in formats.items():
                override = storage.get_voice_normalization(
                    "v5_6_ru-aidar", TextFormat(text_format), language
                )

                assert (
                    override is not None
                ), f"the normalization for {language}/{text_format} was not read at all"
                assert override.type.value == declared["type"]
                assert override.enabled is declared["enabled"]

    def test_a_documented_prompt_is_read(self, tmp_path):
        """A prompt the example references has to be there, or the reference is a lie."""
        example = normalization_example()
        written = yaml.safe_load(example)
        declared = written["models"]["v5_6_ru"]["voices"][0]["normalization"]
        prompt_id = declared["ru"]["text"]["prompt_id"]
        storage = load_example(tmp_path, example, 1)

        assert storage.get_prompt(prompt_id) is not None, f"{prompt_id} was not read"


class TestQwenDocumentation:
    def test_the_readme_no_longer_calls_silero_the_only_implemented_engine(self):
        """A reader must not be told Qwen3-TTS is unavailable when it is served."""
        readme = " ".join(README.read_text().split())

        assert "The Silero TTS Engine is the one implemented today" not in readme
        assert "Silero and Qwen3-TTS" in readme

    def test_the_readme_names_both_supported_qwen_checkpoint_families(self):
        """The Qwen section names Base and CustomVoice, not just the engine family."""
        section = README.read_text().split("#### Qwen3-TTS", 1)[1].split("\n####", 1)[0]

        assert "**Base**" in section
        assert "**CustomVoice**" in section

    def test_the_example_declares_a_base_clone_and_a_custom_voice_speaker(self, tmp_path):
        """The families survive loading with the fields each needs from a Voice."""
        storage = load_example(tmp_path, qwen_models_example(), 0)

        base = storage.get_model_info(QWEN_BASE_MODEL)
        assert base is not None and base.engine_type is EngineType.QWEN3
        base_voice = storage.get_voice(f"{QWEN_BASE_MODEL}-bandit")
        assert base_voice is not None and base_voice.ref_audio and base_voice.ref_text

        custom = storage.get_model_info(QWEN_CUSTOM_VOICE_MODEL)
        assert custom is not None and custom.engine_type is EngineType.QWEN3
        custom_voice = storage.get_voice(f"{QWEN_CUSTOM_VOICE_MODEL}-ryan")
        assert custom_voice is not None and custom_voice.speaker == "Ryan"
        assert custom_voice.instruct

    def test_the_example_shows_an_optional_revision_pin(self, tmp_path):
        """A declared revision reaches the Model Info, and the field is documented."""
        storage = load_example(tmp_path, qwen_models_example(), 0)

        base = storage.get_model_info(QWEN_BASE_MODEL)

        assert base is not None and base.revision
        assert "revision" in documented_fields("Models")

    def test_the_readme_says_where_checkpoints_are_cached(self):
        """The operator is told the directory whose mount preserves the download."""
        readme = README.read_text()

        assert "`<models_dir>/qwen3/<upstream id>`" in readme
        assert "models/qwen3/Qwen/Qwen3-TTS-12Hz-1.7B-Base" in readme

    def test_the_readme_documents_the_dialect_speakers_and_automatic_detection(self):
        """The caveat must be stated, not merely the speaker names and 'automatic'."""
        readme = " ".join(README.read_text().split())

        assert "Dylan" in readme and "Eric" in readme
        assert "automatic-detection mode" in readme
        assert "language_auto_detected: true" in readme


class TestShippedQwenExample:
    def test_the_shipped_example_declares_both_checkpoint_families(self):
        """The same two families ship in the data file, not only in the README."""
        storage = YamlDataStorage(config_path_or_model=DATA_YML, active_models=declared_model_ids())

        base = storage.get_model_info(QWEN_BASE_MODEL)
        assert base is not None and base.engine_type is EngineType.QWEN3
        base_voice = storage.get_voice(f"{QWEN_BASE_MODEL}-bandit")
        assert base_voice is not None and base_voice.ref_audio and base_voice.ref_text

        custom = storage.get_model_info(QWEN_CUSTOM_VOICE_MODEL)
        assert custom is not None and custom.engine_type is EngineType.QWEN3
        custom_voice = storage.get_voice(f"{QWEN_CUSTOM_VOICE_MODEL}-ryan")
        assert custom_voice is not None and custom_voice.speaker == "Ryan"
        assert custom_voice.instruct

    def test_the_shipped_example_is_declared_but_not_activated(self):
        """Declaring a checkpoint must not download it on a fresh boot.

        A Model Info is served only when it is also named in `active_models`, so an
        example that stays out of that list costs nothing until an operator opts in.
        """
        storage = YamlDataStorage(
            config_path_or_model=DATA_YML, active_models=shipped_active_models()
        )

        served_model_ids = {model_info.id for model_info in storage.get_model_infos()}

        assert served_model_ids
        assert QWEN_BASE_MODEL not in served_model_ids
        assert QWEN_CUSTOM_VOICE_MODEL not in served_model_ids


class TestShippedWarmup:
    def test_the_shipped_warmup_models_preserve_startup_behaviour(self):
        """The model warmed before this moved to config.yml is still the one warmed."""
        config = yaml.safe_load(CONFIG_YML.read_text())

        storage = YamlDataStorage(
            config_path_or_model=DATA_YML,
            active_models=config["active_models"],
            warmup_models=config["warmup_models"],
        )

        warmed = [model_info.id for model_info in storage.get_model_infos() if model_info.warmup]

        assert warmed == ["v5_6_ru"]


class TestDocumentedTypesExist:
    def test_no_type_is_documented_that_the_code_has_no_such_type_for(self):
        """A normalization type the enum does not have falls back silently to simple."""
        documented = set(re.findall(r"`(simple|llm|openai)`", README.read_text()))

        assert documented, "the readme documents no normalization type, so nothing is checked"
        assert documented <= {member.value for member in NormalizationType}, (
            f"documented but not a type the code has: "
            f"{sorted(documented - {m.value for m in NormalizationType})}"
        )

    def test_every_type_value_written_in_an_example_is_a_type_the_code_has(self):
        """The same, for the values inside the yaml examples rather than the tables."""
        values = {
            declared["type"]
            for example in yaml_examples(README.read_text())
            for model in yaml.safe_load(example).get("models", {}).values()
            for voice in model.get("voices", [])
            for formats in [voice.get("normalization", {})]
            for by_format in formats.values()
            for declared in by_format.values()
            if declared.get("type") is not None
        }

        assert values, "no example writes a normalization type, so nothing is checked"
        assert values <= {
            member.value for member in NormalizationType
        }, f"an example writes a type the code does not have: {sorted(values)}"


class TestDocumentedTablesMatchTheShapes:
    def test_the_models_table_documents_fields_a_model_info_has(self):
        """A documented key the shape has no field for is a key nothing reads."""
        documented = documented_fields("Models")
        known = set(ModelInfo.__dataclass_fields__) | {"voices"}

        assert documented, "no model fields are documented, so nothing is checked"
        assert (
            documented <= known
        ), f"documented but not a Model Info field: {sorted(documented - known)}"

    def test_the_voices_table_documents_fields_a_voice_has(self):
        """The same for a Voice, minus the ones the code derives rather than reads."""
        documented = documented_fields("Voices")
        known = set(Voice.__dataclass_fields__)

        assert documented, "no voice fields are documented, so nothing is checked"
        assert (
            documented <= known
        ), f"documented but not a Voice field: {sorted(documented - known)}"

    def test_every_documented_normalization_field_names_a_text_format(self):
        """An override is read per Language and Text Format; a key naming neither is dropped.

        A shape without a Text Format level parses into nothing at all, so the key is
        written down and silently ignored.
        """
        documented = documented_fields("Voice normalization")
        text_formats = [member.value for member in TextFormat]

        assert documented, "no normalization fields are documented, so nothing is checked"
        for field in documented:
            assert any(
                text_format in field for text_format in text_formats
            ), f"{field} names no Text Format, so nothing would read it"


class TestDocumentedLayoutMatchesTheServer:
    """The Docker run command the README documents, against how the server lays out."""

    def test_the_image_declares_no_volume_of_its_own(self):
        """A cached model survives a restart only through a mount the run command makes.

        The image bakes nothing: the directory the TTS Engine caches models into is
        created at runtime, so a run command that does not mount it loses them.
        """
        assert "VOLUME" not in DOCKERFILE.read_text()

    def test_the_documented_run_command_mounts_the_models_directory(self):
        """The mount covers the directory the server defaults to, on both sides.

        `./models` is what the server resolves relative to its working directory, and
        `/app` is that working directory in the image — so this is the one pair of
        paths that puts the host's cached models where the server looks.
        """
        assert f"WORKDIR {IMAGE_WORKDIR}" in DOCKERFILE.read_text()
        assert f"./{MODELS_DIR}:{IMAGE_WORKDIR}/{MODELS_DIR}" in README.read_text()

    def test_the_models_directory_is_the_default(self):
        """The mounted directory is the one the server uses when nothing says otherwise."""
        from src.config import Settings

        assert Settings.model_fields["models_dir"].default == MODELS_DIR


class TestDocumentedNameIsTheInstalledOne:
    """The name a reader clones and types is the name the distribution installs."""

    def test_the_documented_command_is_the_installed_command(self):
        assert COMMAND in README.read_text()

    def test_the_documented_clone_url_names_the_project_not_an_engine(self):
        """Cloning must land on the project, whatever engines it aggregates."""
        assert f"{PROJECT_URL}.git" in README.read_text()
        assert "silero-server" not in README.read_text()

    def test_the_documented_image_tag_names_the_project(self):
        assert f"{IMAGE_TAG}:latest" in README.read_text()
