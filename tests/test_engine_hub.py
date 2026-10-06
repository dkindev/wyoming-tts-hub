import pytest

from src.tts.data_storage import YamlDataStorage
from src.tts.models import PredefinedData, TtsResult
from tests.helpers import (
    FakeDataStorage,
    FakeTtsEngine,
    collect_hub_sentences,
    make_model,
    make_voice,
)
from tests.helpers import (
    make_hub as make_tts_hub,
)

MODEL_ID = "v5_5_ru"
VOICE_ID = "v5_5_ru-aidar"
FRAME_DURATION_MS = 50

# A Model id with no Language code in it, so an assertion about a declared Language
# cannot be satisfied by the Model id itself.
LANGUAGE_MODEL_ID = "tts_model"


def make_storage(*, model_id=MODEL_ID, voice_id=VOICE_ID, languages=()):
    """Return storage over one Model declaring `languages`, with one Voice on it."""
    return YamlDataStorage(
        PredefinedData(
            models=[make_model(id=model_id, languages=list(languages))],
            voices=[make_voice(voice_id=voice_id, name="aidar", model=model_id)],
        )
    )


def make_hub(*, engine, frame_duration=FRAME_DURATION_MS, middlewares=(), storage=None):
    """Return a TTS Engine Hub wired to a fake engine for one known Voice and Model."""
    return make_tts_hub(
        engine=engine,
        frame_duration=frame_duration,
        middlewares=middlewares,
        storage=storage if storage is not None else make_storage(),
    )


def make_engine(*, model_id=MODEL_ID, sample_rate=48000, samples_per_sentence=None):
    """Return a FakeTtsEngine holding one second of audio unless told otherwise."""
    return FakeTtsEngine(
        make_model(id=model_id),
        sample_rate=sample_rate,
        samples_per_sentence=(
            samples_per_sentence if samples_per_sentence is not None else sample_rate
        ),
    )


def total_audio_bytes(frames: list[TtsResult]) -> int:
    """Total audio bytes across the frames the Hub emitted."""
    return sum(len(frame.audio) for frame in frames)


class TestSuccessfulSynthesis:
    async def test_known_voice_yields_frames_totalling_engine_output(self):
        """A known Voice yields frames whose audio totals exactly what the engine produced."""
        engine = make_engine(sample_rate=48000)

        frames = await collect_hub_sentences(make_hub(engine=engine), "hello", VOICE_ID)

        assert len(frames) > 0
        assert total_audio_bytes(frames) == engine.audio_size_bytes
        assert engine.synthesized_texts == ["hello"]

    async def test_voice_is_routed_to_the_engine_owning_its_model(self):
        """The Hub asks the Engine Manager for the Model that owns the requested Voice."""
        engine = make_engine()

        await collect_hub_sentences(make_hub(engine=engine), "hello", VOICE_ID)

        assert engine.requests[0][1].id == VOICE_ID

    async def test_frames_carry_wyoming_framing_fields(self):
        """Every frame reports 2 bytes per sample, 1 channel, and the engine's sample rate."""
        engine = make_engine(sample_rate=24000)

        frames = await collect_hub_sentences(make_hub(engine=engine), "hello", VOICE_ID)

        assert len(frames) > 0
        for frame in frames:
            assert frame.sample_rate == 24000
            assert frame.bytes_per_sample == 2
            assert frame.channels == 1

    @pytest.mark.parametrize(
        ("frame_duration_ms", "sample_rate"),
        [
            pytest.param(50, 48000, id="50ms-at-48khz"),
            pytest.param(20, 16000, id="20ms-at-16khz"),
            pytest.param(100, 24000, id="100ms-at-24khz"),
        ],
    )
    async def test_frame_size_matches_configured_frame_duration(
        self, frame_duration_ms, sample_rate
    ):
        """Every full frame holds exactly the audio for one frame_duration of samples."""
        engine = make_engine(sample_rate=sample_rate)
        hub = make_hub(engine=engine, frame_duration=frame_duration_ms)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        expected_frame_samples = int(sample_rate * frame_duration_ms / 1000)
        assert all(len(frame.audio) == expected_frame_samples * 2 for frame in frames)

    async def test_trailing_partial_frame_carries_the_remainder(self):
        """Audio too short to fill whole frames is emitted as one shorter final frame."""
        sample_rate = 48000
        # 1500 samples at 100ms frames of 4800 samples: one partial frame of 1500 samples.
        engine = make_engine(sample_rate=sample_rate, samples_per_sentence=1500)
        hub = make_hub(engine=engine, frame_duration=100)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert len(frames) == 1
        assert len(frames[0].audio) == 1500 * 2

    async def test_audio_spanning_several_frames_is_split_exactly(self):
        """Audio spanning several frames is split without losing or duplicating samples."""
        sample_rate = 48000
        # 12500 samples at 50ms frames of 2400 samples: 5 full frames of 2400, one of 500.
        engine = make_engine(sample_rate=sample_rate, samples_per_sentence=12500)
        hub = make_hub(engine=engine, frame_duration=50)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        frame_samples = [len(frame.audio) // 2 for frame in frames]
        assert frame_samples == [2400, 2400, 2400, 2400, 2400, 500]
        assert total_audio_bytes(frames) == engine.audio_size_bytes


class TestRequestValidation:
    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    async def test_empty_or_whitespace_text_is_rejected(self, text):
        """Empty or whitespace-only text is rejected before any Voice lookup."""
        engine = make_engine()

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(make_hub(engine=engine), text, VOICE_ID)

        assert "empty or whitespace" in str(exc_info.value)
        assert engine.synthesized_texts == []

    async def test_unknown_voice_is_rejected_by_id(self):
        """An unknown Voice is rejected with an error naming that Voice."""
        engine = make_engine()

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(make_hub(engine=engine), "hello", "no_such_voice")

        assert "no_such_voice" in str(exc_info.value)
        assert engine.synthesized_texts == []

    async def test_voice_with_unresolvable_model_is_rejected_by_id(self):
        """A Voice whose Model is absent from storage is rejected naming that Model."""
        orphan_voice = make_voice(voice_id="ghost-voice", name="ghost", model="ghost_model")

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(
                make_hub(engine=make_engine(), storage=FakeDataStorage(voices=[orphan_voice])),
                "hello",
                "ghost-voice",
            )

        assert "ghost_model" in str(exc_info.value)


class TestLanguageValidation:
    """The Hub checks a client-supplied Language against the Model's declared Languages.

    Lands a failing test on purpose (ticket 09): the domain context specifies this
    rejection, and the Hub currently accepts any Language and hands it straight to
    the engine, so a request in a Language the Model cannot speak gets audio back
    with no error.
    """

    async def test_language_the_model_does_not_declare_is_rejected(self):
        """A Language outside the Model's declared Languages is rejected by name.

        The Model id carries no Language code, so "ru" can only reach the error
        message as one of the Model's declared Languages.
        """
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = make_hub(
            engine=engine,
            storage=make_storage(
                model_id=LANGUAGE_MODEL_ID,
                voice_id=f"{LANGUAGE_MODEL_ID}-aidar",
                languages=["ru"],
            ),
        )

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(hub, "hello", f"{LANGUAGE_MODEL_ID}-aidar", language="en")

        message = str(exc_info.value)
        assert "en" in message, "the error must name the requested Language"
        assert "ru" in message, "the error must name the Model's declared Languages"
        assert engine.synthesized_texts == [], "a rejected request must not be synthesized"

    async def test_declared_language_reaches_the_engine(self):
        """A Language the Model declares is accepted and passed through untouched."""
        engine = make_engine()
        hub = make_hub(engine=engine, storage=make_storage(languages=["ru", "en"]))

        await collect_hub_sentences(hub, "hello", VOICE_ID, language="en")

        assert engine.languages == ["en"]


class TestMiddlewareChain:
    async def test_middlewares_run_in_order_before_synthesis(self):
        """The middleware chain runs in order, and the last one still reaches synthesis."""
        calls: list[str] = []

        def make_middleware(name):
            async def middleware(ctx, next_call):
                calls.append(f"before-{name}")
                await next_call()
                calls.append(f"after-{name}")

            return middleware

        engine = make_engine()
        hub = make_hub(
            engine=engine,
            middlewares=[make_middleware("outer"), make_middleware("inner")],
        )

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert calls == ["before-outer", "before-inner", "after-inner", "after-outer"]
        assert total_audio_bytes(frames) == engine.audio_size_bytes

    async def test_middleware_can_replace_the_text_sent_to_the_engine(self):
        """A middleware that rewrites ctx.sentences changes what the engine synthesizes."""

        async def uppercase_middleware(ctx, next_call):
            ctx.sentences = _as_sentence_stream(ctx.raw_text.upper())
            await next_call()

        engine = make_engine()
        hub = make_hub(engine=engine, middlewares=[uppercase_middleware])

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert engine.synthesized_texts == ["HELLO"]


async def _as_sentence_stream(text):
    yield text
