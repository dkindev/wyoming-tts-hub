import numpy as np
import pytest

from src.tts.data_storage import YamlDataStorage
from src.tts.middleware import ResolveLanguageMiddleware
from src.tts.models import PredefinedData, TtsResult
from tests.helpers import (
    FakeDataStorage,
    FakeEngineManager,
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

# The Model every request is served by declares exactly this Language, which the
# resolving middleware fills in when a request carries none.
SOLE_LANGUAGE = "ru"

# A Model id with no Language code in it, so an assertion about a declared Language
# cannot be satisfied by the Model id itself.
LANGUAGE_MODEL_ID = "tts_model"
LANGUAGE_VOICE_ID = f"{LANGUAGE_MODEL_ID}-aidar"


def make_storage(
    *, model_id=MODEL_ID, voice_id=VOICE_ID, languages=(SOLE_LANGUAGE,), auto_detected=False
):
    """Return storage over one Model declaring `languages`, with one Voice on it."""
    return YamlDataStorage(
        PredefinedData(
            models=[
                make_model(
                    id=model_id,
                    languages=list(languages),
                    language_auto_detected=auto_detected,
                )
            ],
            voices=[make_voice(voice_id=voice_id, name="aidar", model=model_id)],
        )
    )


def make_hub(
    *,
    engine,
    frame_duration=FRAME_DURATION_MS,
    middlewares=None,
    storage=None,
    engine_manager=None,
):
    """Return a TTS Engine Hub wired to a fake engine for one known Voice and Model."""
    return make_tts_hub(
        engine=engine,
        frame_duration=frame_duration,
        middlewares=(
            middlewares if middlewares is not None else [ResolveLanguageMiddleware().invoke]
        ),
        storage=storage if storage is not None else make_storage(),
        engine_manager=engine_manager,
    )


def make_engine(
    *,
    model_id=MODEL_ID,
    sample_rate=48000,
    samples_per_sentence=None,
    bytes_per_sample=2,
    channels=1,
):
    """Return a FakeTtsEngine holding one second of audio unless told otherwise."""
    return FakeTtsEngine(
        make_model(id=model_id),
        sample_rate=sample_rate,
        samples_per_sentence=(
            samples_per_sentence if samples_per_sentence is not None else sample_rate
        ),
        bytes_per_sample=bytes_per_sample,
        channels=channels,
    )


def total_audio_bytes(frames: list[TtsResult]) -> int:
    """Total audio bytes across the frames the Hub emitted."""
    return sum(frame.audio.nbytes for frame in frames)


class TestSuccessfulSynthesis:
    async def test_known_voice_yields_frames_totalling_engine_output(self):
        """A known Voice yields frames whose audio totals exactly what the engine produced."""
        engine = make_engine(sample_rate=48000)

        frames = await collect_hub_sentences(make_hub(engine=engine), "hello", VOICE_ID)

        assert len(frames) > 0
        assert total_audio_bytes(frames) == engine.audio_size_bytes
        assert engine.synthesized_texts == ["hello"]

    async def test_frames_are_views_over_the_engines_audio(self):
        """Every frame of a Sentence addresses the Engine's own buffer, copying nothing.

        Frames are checked against the buffer the Engine emitted rather than with
        `np.shares_memory` between frames, because consecutive frames cover disjoint
        ranges of it.
        """
        engine = make_engine(sample_rate=48000, samples_per_sentence=12500)

        frames = await collect_hub_sentences(make_hub(engine=engine), "hello", VOICE_ID)

        assert len(engine.emitted_audio) == 1
        assert len(frames) > 1
        synthesized = engine.emitted_audio[0]
        assert all(np.shares_memory(frame.audio, synthesized) for frame in frames)

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

    async def test_frames_carry_the_chunks_own_format(self):
        """A Chunk that is not 16-bit mono is framed with the width and channels it declares."""
        engine = make_engine(sample_rate=48000, bytes_per_sample=4, channels=2)
        hub = make_hub(engine=engine, frame_duration=50)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert len(frames) > 0
        for frame in frames:
            assert frame.bytes_per_sample == 4
            assert frame.channels == 2

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
        assert [len(frame.audio) for frame in frames] == [expected_frame_samples] * len(frames)

    async def test_trailing_partial_frame_carries_the_remainder(self):
        """Audio too short to fill whole frames is emitted as one shorter final frame."""
        sample_rate = 48000
        # 1500 samples at 100ms frames of 4800 samples: one partial frame of 1500 samples.
        engine = make_engine(sample_rate=sample_rate, samples_per_sentence=1500)
        hub = make_hub(engine=engine, frame_duration=100)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert [len(frame.audio) for frame in frames] == [1500]

    async def test_audio_spanning_several_frames_is_split_exactly(self):
        """Audio spanning several frames is split without losing or duplicating samples."""
        sample_rate = 48000
        # 12500 samples at 50ms frames of 2400 samples: 5 full frames of 2400, one of 500.
        engine = make_engine(sample_rate=sample_rate, samples_per_sentence=12500)
        hub = make_hub(engine=engine, frame_duration=50)

        frames = await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert [len(frame.audio) for frame in frames] == [2400, 2400, 2400, 2400, 2400, 500]
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
    """The Hub checks the request's Language against the Model's declared Languages.

    The Language is inspected as it stands after the middleware chain, so a
    middleware is trusted to have resolved it.
    """

    def make_language_hub(self, *, engine, languages, auto_detected=False):
        """Return a Hub serving a Model whose id carries no Language code."""
        return make_hub(
            engine=engine,
            storage=make_storage(
                model_id=LANGUAGE_MODEL_ID,
                voice_id=LANGUAGE_VOICE_ID,
                languages=languages,
                auto_detected=auto_detected,
            ),
        )

    async def test_language_the_model_does_not_declare_is_rejected(self):
        """A Language outside the Model's declared Languages is rejected by name.

        The Model id carries no Language code, so "ru" can only reach the error
        message as one of the Model's declared Languages.
        """
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=["ru"])

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID, language="en")

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

    async def test_absent_language_is_filled_in_from_the_models_sole_language(self):
        """No Language against a Model declaring one Language synthesizes in that Language."""
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=["ru"])

        await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID)

        assert engine.languages == ["ru"]

    async def test_absent_language_reaches_no_engine_for_an_auto_detecting_model(self):
        """A Model that auto-detects is asked to synthesize without a Language."""
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=["ru"], auto_detected=True)

        await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID)

        assert engine.languages == [None]

    @pytest.mark.parametrize(
        ("auto_detected", "expected"),
        [
            pytest.param(False, "error", id="model-does-not-auto-detect"),
            pytest.param(True, "audio", id="model-auto-detects"),
        ],
    )
    async def test_absent_language_against_several_declared_languages(
        self, auto_detected, expected
    ):
        """Several declared Languages leave nothing to resolve from, unless auto-detected.

        The Model declares `ru` and `en`, and its id carries no Language code, so both
        can only reach the error message as declared Languages.
        """
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(
            engine=engine, languages=["ru", "en"], auto_detected=auto_detected
        )

        if expected == "error":
            with pytest.raises(ValueError) as exc_info:
                await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID)

            message = str(exc_info.value)
            assert "ru" in message, "the error must name every declared Language"
            assert "en" in message, "the error must name every declared Language"
            assert engine.synthesized_texts == []
        else:
            await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID)

            assert engine.languages == [None]

    async def test_absent_language_against_a_model_declaring_none_is_rejected(self):
        """Nothing to validate against and nothing to resolve from is still an error."""
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=[])

        with pytest.raises(ValueError):
            await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID)

        assert engine.synthesized_texts == []

    async def test_language_against_a_model_declaring_none_is_rejected_as_uncheckable(self):
        """With nothing to validate against, the error blames the Model, not the request.

        A Language was supplied here, so saying none was given would send whoever is
        debugging it looking in the wrong place.
        """
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=[])

        with pytest.raises(ValueError) as exc_info:
            await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID, language="en")

        message = str(exc_info.value)
        assert "en" in message, "the error must name the requested Language"
        assert "declares no Languages" in message
        assert engine.synthesized_texts == []

    async def test_language_against_an_auto_detecting_model_declaring_none_is_accepted(self):
        """Nothing to validate against, and the Model decides for itself, so it proceeds."""
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        hub = self.make_language_hub(engine=engine, languages=[], auto_detected=True)

        await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID, language="en")

        assert engine.languages == ["en"]

    async def test_language_survives_the_middleware_chain_unmodified(self):
        """A Language the client supplied is what the engine is asked for."""
        engine = make_engine()
        seen_languages = []

        async def record_language(ctx, next_call):
            seen_languages.append(ctx.language)
            await next_call()

        hub = make_hub(
            engine=engine,
            middlewares=[ResolveLanguageMiddleware().invoke, record_language],
            storage=make_storage(languages=["ru", "en"]),
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID, language="en")

        assert seen_languages == ["en"]
        assert engine.languages == ["en"]

    async def test_rejected_request_never_acquires_an_engine_context(self):
        """Validation runs before the engine context is acquired, so the Model is not loaded."""
        engine = make_engine(model_id=LANGUAGE_MODEL_ID)
        engine_manager = FakeEngineManager({LANGUAGE_MODEL_ID: engine})
        hub = make_hub(
            engine=engine,
            storage=make_storage(
                model_id=LANGUAGE_MODEL_ID, voice_id=LANGUAGE_VOICE_ID, languages=["ru"]
            ),
            engine_manager=engine_manager,
        )

        with pytest.raises(ValueError):
            await collect_hub_sentences(hub, "hello", LANGUAGE_VOICE_ID, language="en")

        assert engine_manager.requested_model_ids == []
        assert engine.warmup_count == 0


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
            middlewares=[
                ResolveLanguageMiddleware().invoke,
                make_middleware("outer"),
                make_middleware("inner"),
            ],
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
        hub = make_hub(
            engine=engine,
            middlewares=[ResolveLanguageMiddleware().invoke, uppercase_middleware],
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert engine.synthesized_texts == ["HELLO"]


async def _as_sentence_stream(text):
    yield text
