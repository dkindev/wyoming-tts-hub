import hashlib
import os

import yaml

from src.tts.models import EngineType, Model, TextFormat, Voice


def hash_models_yml(yml_path: str) -> str:
    """Compute SHA256 hex digest of a models.yml file."""
    hasher = hashlib.sha256()
    with open(yml_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def models_yml_path(models_dir: str) -> str:
    """Return the path to models.yml within the silero subdirectory."""
    return os.path.join(models_dir, "silero", "models.yml")


def make_models_dir(
    tmp_path,
    sample_rates=None,
    model_name="v5_5_ru",
    language="ru",
    yml_content=None,
    pt_content=b"fake model",
):
    """Create a models directory with pre-populated models.yml and .pt files.

    Args:
        tmp_path: Temporary path root (from pytest tmp_path fixture).
        sample_rates: List of sample rates for the model. Defaults to [48000].
        model_name: Name of the model. Defaults to "v5_5_ru".
        language: Language code. Defaults to "ru".
        yml_content: Optional custom models.yml content as bytes. When provided,
            replaces the auto-generated YAML with this content and uses the
            default model_name/language in the path.
        pt_content: Optional model .pt file content. Defaults to b"fake model".

    Returns:
        The models_dir path (str), with models.yml at {models_dir}/silero/models.yml
        and the model .pt file at {models_dir}/silero/{language}/{model_name}.pt.
    """
    if sample_rates is None:
        sample_rates = [48000]
    rates_str = ", ".join(str(r) for r in sample_rates)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    silero_dir = models_dir / "silero"
    silero_dir.mkdir()
    if yml_content is not None:
        (silero_dir / "models.yml").write_bytes(yml_content)
    else:
        yml = (
            f"tts_models:\n  {language}:\n    {model_name}:\n"
            f"      latest:\n"
            f"        package: 'http://x'\n"
            f"        sample_rate: [{rates_str}]\n"
        )
        (silero_dir / "models.yml").write_text(yml)
    lang_dir = silero_dir / language
    lang_dir.mkdir()
    (lang_dir / f"{model_name}.pt").write_bytes(pt_content)
    return str(models_dir)


def make_config_file(tmp_path, models=None):
    """Create a temp config file with merged structure."""
    config_yml = tmp_path / "config.yml"
    config_data = {"models": models or {}}
    config_yml.write_text(yaml.dump(config_data))
    return str(config_yml)


def make_voice(*, voice_id, name, speaker=None, model="v5_5_ru"):
    return Voice(
        id=voice_id,
        name=name,
        speaker=speaker or name,
        model_id=model,
    )


def make_model(
    id="v5_5_ru",
    engine_type=EngineType.SILERO,
    languages=None,
    ssml_supported=False,
    warmup=False,
    enabled=True,
):
    return Model(
        id=id,
        engine_type=engine_type,
        languages=languages if languages is not None else [],
        ssml_supported=ssml_supported,
        warmup=warmup,
        enabled=enabled,
    )


def make_merged_yaml(tmp_path, models_data: dict) -> str:
    """Write a merged-structure config YAML and return its path."""
    config_yml = tmp_path / "config.yml"
    config_yml.write_text(yaml.dump({"models": models_data}))
    return str(config_yml)


async def collect_hub_sentences(hub, text, voice_id, input_type=TextFormat.TEXT):
    """Collect all TtsResult chunks yielded by the Engine Hub's synthesize_pcm_chunks."""
    return [chunk async for chunk in hub.synthesize_pcm_chunks(text, voice_id, input_type)]
