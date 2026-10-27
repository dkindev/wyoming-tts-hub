import json
import os
import unittest.mock

import numpy as np
import pytest
import torch

from src.tts.models import EngineType, ModelInfo, TextFormat, Voice
from src.tts.qwen3_engine import Qwen3TtsEngine

MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
VOICE_ID = f"{MODEL_ID}-clone"
SAMPLE_RATE = 24000


class FakeQwenModel:
    """A loaded Qwen3-TTS model that records what the engine asks of it."""

    def __init__(
        self,
        audio=None,
        sample_rate=SAMPLE_RATE,
        supported_speakers=None,
        supported_languages=None,
    ):
        self.audio = np.array([0.0, 0.5, -0.5], dtype=np.float32) if audio is None else audio
        self.sample_rate = sample_rate
        self.supported_speakers = supported_speakers
        self.supported_languages = supported_languages
        self.prompt_calls: list[dict] = []
        self.generate_calls: list[dict] = []
        self.custom_voice_calls: list[dict] = []

    def create_voice_clone_prompt(self, **kwargs):
        self.prompt_calls.append(kwargs)
        return [{"prompt": "built"}]

    def generate_voice_clone(self, **kwargs):
        self.generate_calls.append(kwargs)
        return [self.audio], self.sample_rate

    def generate_custom_voice(self, **kwargs):
        self.custom_voice_calls.append(kwargs)
        return [self.audio], self.sample_rate

    def get_supported_speakers(self):
        return self.supported_speakers

    def get_supported_languages(self):
        return self.supported_languages


def make_engine(tmp_path, *, model_id=MODEL_ID, upstream_id=None, revision=None, device="cpu"):
    model_info = ModelInfo(
        id=model_id,
        engine_type=EngineType.QWEN3,
        upstream_id=upstream_id,
        languages=["en"],
        revision=revision,
    )
    return Qwen3TtsEngine(
        model_info=model_info,
        device=device,
        models_dir=str(tmp_path / "models"),
    )


def write_checkpoint(model_type="base", model_size=None):
    """Return a snapshot_download stand-in that lays down a checkpoint config."""

    def download(*, repo_id, revision, local_dir):
        os.makedirs(local_dir, exist_ok=True)
        config = {"tts_model_type": model_type, "tts_model_size": model_size}
        with open(os.path.join(local_dir, "config.json"), "w", encoding="utf-8") as config_file:
            json.dump(config, config_file)

        return local_dir

    return download


async def warmup(engine, fake_model, model_type="base", model_size=None):
    """Warm `engine` against a fake downloaded checkpoint and loaded model."""
    with (
        unittest.mock.patch(
            "src.tts.qwen3_engine.snapshot_download",
            side_effect=write_checkpoint(model_type, model_size),
        ) as download,
        unittest.mock.patch(
            "src.tts.qwen3_engine.Qwen3TTSModel.from_pretrained",
            return_value=fake_model,
        ) as from_pretrained,
    ):
        await engine.warmup()

    return download, from_pretrained


def make_voice(*, ref_audio="reference.wav", ref_text="Reference text"):
    return Voice(
        id=VOICE_ID,
        name="clone",
        speaker="clone",
        model_id=MODEL_ID,
        ref_audio=ref_audio,
        ref_text=ref_text,
    )


def make_custom_voice(*, speaker="Vivian", instruct=None):
    return Voice(
        id=f"{MODEL_ID}-preset",
        name="preset",
        speaker=speaker,
        model_id=MODEL_ID,
        instruct=instruct,
    )


async def synthesize(engine, voice, *, text="Hello", language="en"):
    return [
        result async for result in engine.synthesize_pcm(text, voice, TextFormat.TEXT, language)
    ]


@pytest.mark.asyncio
class TestWarmup:
    async def test_downloads_the_checkpoint_into_the_qwen3_directory(self, tmp_path):
        """The upstream id is fetched into the configured Models directory under qwen3."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()

        download, from_pretrained = await warmup(engine, fake)

        download.assert_called_once()
        call = download.call_args.kwargs
        assert call["repo_id"] == MODEL_ID
        assert call["revision"] is None
        assert call["local_dir"] == os.path.join(engine._models_dir, "qwen3", MODEL_ID)

        from_pretrained.assert_called_once()
        loaded_path = from_pretrained.call_args.args[0]
        assert loaded_path == call["local_dir"]
        assert from_pretrained.call_args.kwargs["device_map"] == "cpu"
        assert engine.device == torch.device("cpu")

    async def test_fetches_the_upstream_artifact_named_by_upstream_id(self, tmp_path):
        """A local id with an upstream_id fetches and caches the upstream artifact."""
        local_id = "bandit"
        upstream_id = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        engine = make_engine(tmp_path, model_id=local_id, upstream_id=upstream_id)

        download, from_pretrained = await warmup(engine, FakeQwenModel())

        call = download.call_args.kwargs
        assert call["repo_id"] == upstream_id
        assert call["local_dir"] == os.path.join(engine._models_dir, "qwen3", upstream_id)
        assert from_pretrained.call_args.args[0] == call["local_dir"]
        assert engine.model_info.id == local_id

    async def test_blank_upstream_id_falls_back_to_the_local_id(self, tmp_path):
        """A directly built Model Info with a blank upstream_id fetches under its id."""
        engine = make_engine(tmp_path, upstream_id="   ")

        download, from_pretrained = await warmup(engine, FakeQwenModel())

        call = download.call_args.kwargs
        assert call["repo_id"] == MODEL_ID
        assert call["local_dir"] == os.path.join(engine._models_dir, "qwen3", MODEL_ID)
        assert from_pretrained.call_args.args[0] == call["local_dir"]

    async def test_download_failure_names_the_local_id_not_the_upstream_id(self, tmp_path):
        """A failed fetch is reported against the id the operator configured."""
        local_id = "bandit"
        upstream_id = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
        engine = make_engine(tmp_path, model_id=local_id, upstream_id=upstream_id)

        with unittest.mock.patch(
            "src.tts.qwen3_engine.snapshot_download",
            side_effect=RuntimeError("connection failed"),
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await engine.warmup()

        message = str(exc_info.value)
        assert local_id in message
        assert upstream_id not in message

    async def test_downloads_the_declared_revision(self, tmp_path):
        """A Model Info naming a revision asks upstream for that commit."""
        engine = make_engine(tmp_path, revision="0123456789abcdef")
        fake = FakeQwenModel()

        download, _ = await warmup(engine, fake)

        assert download.call_args.kwargs["revision"] == "0123456789abcdef"

    async def test_loads_on_the_resolved_device(self, tmp_path):
        """The resolved device, not the configured string, is handed to the loader."""
        engine = make_engine(tmp_path, device="cuda")
        fake = FakeQwenModel()
        available_cuda = unittest.mock.MagicMock()
        available_cuda.is_available.return_value = True

        with unittest.mock.patch.object(torch, "cuda", available_cuda):
            _, from_pretrained = await warmup(engine, fake)

        assert from_pretrained.call_args.kwargs["device_map"] == "cuda"
        assert engine.device == torch.device("cuda")

    async def test_base_checkpoint_is_accepted(self, tmp_path):
        """A Base checkpoint is the family this engine warms up and clones with."""
        engine = make_engine(tmp_path)

        await warmup(engine, FakeQwenModel())

        assert engine._checkpoint_family == "base"

    async def test_custom_voice_checkpoint_is_accepted(self, tmp_path):
        """A CustomVoice checkpoint is served by the same TTS Engine as a Base one."""
        engine = make_engine(tmp_path)

        await warmup(engine, FakeQwenModel(), model_type="custom_voice")

        assert engine._checkpoint_family == "custom_voice"

    async def test_unsupported_checkpoint_family_is_rejected_before_loading(self, tmp_path):
        """A VoiceDesign checkpoint is refused by name, without paying for a load."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()

        with (
            unittest.mock.patch(
                "src.tts.qwen3_engine.snapshot_download",
                side_effect=write_checkpoint("voice_design"),
            ),
            unittest.mock.patch(
                "src.tts.qwen3_engine.Qwen3TTSModel.from_pretrained",
                return_value=fake,
            ) as from_pretrained,
            pytest.raises(RuntimeError) as exc_info,
        ):
            await engine.warmup()

        cause = exc_info.value.__cause__
        assert type(cause) is RuntimeError
        message = str(cause)
        assert "VoiceDesign" in message
        assert "Base" in message
        assert "CustomVoice" in message
        from_pretrained.assert_not_called()

    async def test_synthesis_with_an_unsupported_family_is_a_plain_runtime_error(self, tmp_path):
        """A checkpoint that slipped past warmup is refused with the shared error type."""
        engine = make_engine(tmp_path)
        await warmup(engine, FakeQwenModel())
        engine._checkpoint_family = "voice_design"

        with pytest.raises(RuntimeError) as exc_info:
            await synthesize(engine, make_voice())

        assert type(exc_info.value) is RuntimeError
        assert "does not support synthesis" in str(exc_info.value)


@pytest.mark.asyncio
class TestLanguageMapping:
    @pytest.mark.parametrize(
        ("code", "name"),
        [
            ("en", "English"),
            ("ru", "Russian"),
            ("zh-CN", "Chinese"),
            ("fr", "French"),
            ("de", "German"),
            ("es", "Spanish"),
            ("it", "Italian"),
            ("pt", "Portuguese"),
            ("ja", "Japanese"),
            ("ko", "Korean"),
        ],
    )
    async def test_maps_language_codes_to_checkpoint_names(self, tmp_path, code, name):
        """A project Language code reaches the checkpoint as its English language name."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)

        await synthesize(engine, make_voice(), language=code)

        assert fake.generate_calls[0]["language"] == name

    async def test_unknown_language_falls_back_to_automatic_detection(self, tmp_path):
        """An unrecognised code asks for automatic detection and warns instead of failing."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)

        with unittest.mock.patch("src.tts.qwen3_engine.logger.warning") as warning:
            await synthesize(engine, make_voice(), language="xx")

        assert fake.generate_calls[0]["language"] == "Auto"
        warning.assert_called_once()
        assert "xx" in str(warning.call_args)

    async def test_an_omitted_language_requests_automatic_detection(self, tmp_path):
        """No Language at all is the checkpoint's automatic mode, without a warning."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)

        with unittest.mock.patch("src.tts.qwen3_engine.logger.warning") as warning:
            await synthesize(engine, make_voice(), language=None)

        assert fake.generate_calls[0]["language"] == "Auto"
        warning.assert_not_called()


@pytest.mark.asyncio
class TestVoiceCloning:
    async def test_synthesizes_with_a_voice_prompt_built_from_the_reference(self, tmp_path):
        """Reference Audio and text build the prompt the checkpoint synthesizes with."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)
        voice = make_voice()

        results = await synthesize(engine, voice, text="Hello there")

        assert fake.prompt_calls == [
            {
                "ref_audio": "reference.wav",
                "ref_text": "Reference text",
                "x_vector_only_mode": False,
            }
        ]
        call = fake.generate_calls[0]
        assert call["text"] == "Hello there"
        assert call["voice_clone_prompt"] == [{"prompt": "built"}]
        assert results[0].sample_rate == SAMPLE_RATE

    async def test_reuses_the_voice_prompt_for_later_sentences(self, tmp_path):
        """The Voice Prompt is built once per Voice, not once per Sentence."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)
        voice = make_voice()

        await synthesize(engine, voice, text="First sentence")
        await synthesize(engine, voice, text="Second sentence")

        assert len(fake.prompt_calls) == 1
        assert len(fake.generate_calls) == 2

    async def test_reference_audio_without_text_clones_from_the_speaker_embedding(self, tmp_path):
        """A Voice with no reference text uses speaker-embedding-only cloning and warns."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)

        with unittest.mock.patch("src.tts.qwen3_engine.logger.warning") as warning:
            await synthesize(engine, make_voice(ref_text=None))

        assert fake.prompt_calls[0]["x_vector_only_mode"] is True
        assert fake.prompt_calls[0]["ref_text"] is None
        warning.assert_called_once()
        assert "quality" in str(warning.call_args).lower()

    async def test_a_base_voice_without_reference_audio_is_a_configuration_error(self, tmp_path):
        """A Base Voice that names no Reference Audio is refused by name."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel()
        await warmup(engine, fake)
        voice = make_voice(ref_audio=None)

        with pytest.raises(ValueError) as exc_info:
            await synthesize(engine, voice)

        assert voice.id in str(exc_info.value)
        assert fake.prompt_calls == []


@pytest.mark.asyncio
class TestCustomVoice:
    async def test_dispatches_a_custom_voice_checkpoint_to_the_speaker_api(self, tmp_path):
        """A CustomVoice checkpoint synthesizes from its Speaker, not from a Voice Prompt."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["english"])
        await warmup(engine, fake, model_type="custom_voice")
        voice = make_custom_voice()

        await synthesize(engine, voice, text="Hello there")

        assert fake.prompt_calls == []
        assert fake.generate_calls == []
        assert fake.custom_voice_calls[0]["text"] == "Hello there"
        assert fake.custom_voice_calls[0]["speaker"] == "Vivian"

    async def test_passes_the_voices_instruction_through(self, tmp_path):
        """An instruction declared on a Voice reaches the checkpoint unchanged."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["english"])
        await warmup(engine, fake, model_type="custom_voice")

        await synthesize(engine, make_custom_voice(instruct="Speak angrily"))

        assert fake.custom_voice_calls[0]["instruct"] == "Speak angrily"

    async def test_an_absent_instruction_is_passed_as_none(self, tmp_path):
        """A Voice without an instruction does not invent one."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["english"])
        await warmup(engine, fake, model_type="custom_voice")

        await synthesize(engine, make_custom_voice())

        assert fake.custom_voice_calls[0]["instruct"] is None

    async def test_maps_the_language_for_custom_voice(self, tmp_path):
        """A CustomVoice checkpoint receives the checkpoint's name for the Language."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["russian"])
        await warmup(engine, fake, model_type="custom_voice")

        await synthesize(engine, make_custom_voice(), language="ru")

        assert fake.custom_voice_calls[0]["language"] == "Russian"

    async def test_an_unsupported_speaker_is_refused_by_name(self, tmp_path):
        """A Speaker the checkpoint does not publish is an error naming the value."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian", "ryan"])
        await warmup(engine, fake, model_type="custom_voice")
        voice = make_custom_voice(speaker="Nobody")

        with pytest.raises(ValueError) as exc_info:
            await synthesize(engine, voice)

        message = str(exc_info.value)
        assert "Nobody" in message
        assert "vivian" in message
        assert fake.custom_voice_calls == []

    async def test_an_unknown_language_code_is_refused_by_name(self, tmp_path):
        """A Language code the engine cannot translate is an error, not automatic detection."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"])
        await warmup(engine, fake, model_type="custom_voice")

        with pytest.raises(ValueError) as exc_info:
            await synthesize(engine, make_custom_voice(), language="xx")

        assert "xx" in str(exc_info.value)
        assert fake.custom_voice_calls == []

    async def test_a_language_the_checkpoint_rejects_is_refused_by_name(self, tmp_path):
        """A mapped Language the checkpoint does not publish is an error naming it."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["english", "auto"])
        await warmup(engine, fake, model_type="custom_voice")

        with pytest.raises(ValueError) as exc_info:
            await synthesize(engine, make_custom_voice(), language="ru")

        message = str(exc_info.value)
        assert "ru" in message
        assert "Russian" in message
        assert fake.custom_voice_calls == []

    async def test_warns_when_the_checkpoint_size_ignores_an_instruction(self, tmp_path):
        """A 0.6B CustomVoice checkpoint ignores instructions, so the operator is warned."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"], supported_languages=["english"])
        await warmup(engine, fake, model_type="custom_voice", model_size="0b6")

        with unittest.mock.patch("src.tts.qwen3_engine.logger.warning") as warning:
            await synthesize(engine, make_custom_voice(instruct="Speak angrily"))
            await synthesize(engine, make_custom_voice(instruct="Speak angrily"))

        warning.assert_called_once()
        assert "instruction" in str(warning.call_args).lower()
        assert [call["instruct"] for call in fake.custom_voice_calls] == [None, None]

    async def test_a_voice_without_a_speaker_is_a_configuration_error(self, tmp_path):
        """A CustomVoice Voice that names no Speaker is refused by name."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(supported_speakers=["vivian"])
        await warmup(engine, fake, model_type="custom_voice")
        voice = make_custom_voice(speaker="")

        with pytest.raises(ValueError) as exc_info:
            await synthesize(engine, voice)

        assert voice.id in str(exc_info.value)
        assert fake.custom_voice_calls == []


@pytest.mark.asyncio
class TestAudioConversion:
    async def test_outputs_mono_16_bit_pcm_at_the_checkpoint_sample_rate(self, tmp_path):
        """Samples are clamped and written as mono 16-bit PCM at the model's own rate."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(
            audio=np.array([-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5], dtype=np.float32)
        )
        await warmup(engine, fake)

        results = await synthesize(engine, make_voice())

        result = results[0]
        assert result.sample_rate == SAMPLE_RATE
        assert result.bytes_per_sample == 2
        assert result.channels == 1
        assert result.audio.dtype == np.int16
        assert result.audio.tolist() == [-32767, -32767, -16383, 0, 16383, 32767, 32767]

    async def test_stereo_output_is_downmixed_to_one_channel(self, tmp_path):
        """Audio carrying more than one channel is averaged down to mono."""
        engine = make_engine(tmp_path)
        fake = FakeQwenModel(
            audio=np.array([[0.0, 1.0], [0.5, 0.5], [1.0, -1.0]], dtype=np.float32)
        )
        await warmup(engine, fake)

        results = await synthesize(engine, make_voice())

        assert results[0].channels == 1
        assert results[0].audio.tolist() == [16383, 16383, 0]
