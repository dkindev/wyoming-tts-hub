import numpy as np

from src.tts.models import TextFormat
from tests.helpers import FakeTtsEngine, make_model_info, make_voice, sample_index_audio

MODEL_ID = "v5_5_ru"


def make_engine(**kwargs):
    """Return a FakeTtsEngine for one Model Info, with a Voice that points at it."""
    voice = make_voice(voice_id=f"ru_RU-{MODEL_ID}-aidar", name="aidar", model=MODEL_ID)
    engine = FakeTtsEngine(make_model_info(id=MODEL_ID), **kwargs)
    return engine, voice


async def synthesize(engine, voice):
    """Synthesize one sentence through `engine` and return the yielded Chunks."""
    return [chunk async for chunk in engine.synthesize_pcm("Привет", voice, TextFormat.TEXT)]


class TestContiguousAudio:
    """Audio a TTS Engine yields is addressable as raw bytes, whatever layout it synthesized."""

    async def test_audio_is_c_contiguous(self):
        """Audio the TTS Engine synthesized with gaps between samples reaches the caller contiguous."""
        engine, voice = make_engine(strided_audio=True)

        chunks = await synthesize(engine, voice)

        assert len(chunks) == 1
        assert chunks[0].audio.flags["C_CONTIGUOUS"]

    async def test_audio_samples_are_the_ones_synthesized(self):
        """Making the audio contiguous leaves every sample, and the Sample Rate, as synthesized."""
        engine, voice = make_engine(strided_audio=True)

        chunks = await synthesize(engine, voice)

        assert chunks[0].sample_rate == engine.sample_rate
        assert chunks[0].bytes_per_sample == 2
        assert chunks[0].channels == 1
        assert np.array_equal(
            chunks[0].audio, sample_index_audio(engine.samples_per_sentence, engine.sample_dtype)
        )
