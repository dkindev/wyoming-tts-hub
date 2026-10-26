import numpy as np
import pytest
from wyoming.audio import AudioChunk, AudioStart
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeTextFormat,
    SynthesizeVoice,
)

from src import PROJECT_NAME, __metadata__
from src.handler import TtsEngineHubEventHandler
from src.tts.data_storage import YamlDataStorage
from src.tts.middleware import ResolveLanguageMiddleware
from src.tts.models import ENGINE_REPO_URLS, EngineType, PredefinedData, TtsResult
from tests.helpers import (
    FakeDataStorage,
    FakeTtsEngine,
    WyomingClient,
    announced_audio_format,
    audio_formats,
    make_hub,
    make_model_info,
    make_voice,
    sample_index_audio,
    streamed_audio_bytes,
)

SERVICE_NAME = "wyoming-tts-hub"
MODEL_ID = "v5_6_ru"
VOICE_ID = "v5_6_ru-aidar"
OTHER_MODEL_ID = "v3_en"
SAMPLE_RATE = 24000
FRAME_DURATION_MS = 50
LANGUAGE = "ru"
OTHER_LANGUAGE = "en"

# The fake engine holds one second of audio, so the frame duration decides how
# many `audio-chunk` events the Hub hands the handler: 1000ms / 50ms = 20.
CHUNK_EVENTS_PER_REQUEST = 1000 // FRAME_DURATION_MS

FAILURE = "engine exploded"


class ExplodingTtsEngine(FakeTtsEngine):
    """A TTS Engine that fails on every synthesis, standing in for a broken engine."""

    async def _synthesize_pcm(self, text, voice, text_format, language=None):
        raise RuntimeError(FAILURE)
        yield  # pragma: no cover - unreachable, but makes this an async generator


class NoSampleAxisTtsEngine(FakeTtsEngine):
    """A TTS Engine that hands over audio with no sample axis to frame."""

    async def _synthesize_pcm(self, text, voice, text_format, language=None):
        yield TtsResult(
            audio=np.zeros((), dtype=np.int16),
            sample_rate=self.sample_rate,
            bytes_per_sample=2,
            channels=1,
        )


def make_storage(*, active_models=(MODEL_ID,), languages=(LANGUAGE,), ssml_supported=False):
    """Return storage over two Model Infos, serving only the Active Models' Voices."""
    return YamlDataStorage(
        PredefinedData(
            models=[
                make_model_info(
                    id=MODEL_ID, languages=list(languages), ssml_supported=ssml_supported
                ),
                make_model_info(id=OTHER_MODEL_ID, languages=["en"]),
            ],
            voices=[
                make_voice(voice_id=f"{MODEL_ID}-zebra", name="zebra", model=MODEL_ID),
                make_voice(voice_id=f"{MODEL_ID}-aidar", name="aidar", model=MODEL_ID),
                make_voice(voice_id=f"{OTHER_MODEL_ID}-en_0", name="en_0", model=OTHER_MODEL_ID),
            ],
        ),
        active_models=list(active_models),
    )


def make_engine(*, sample_rate=SAMPLE_RATE, **kwargs):
    """Return a fake TTS Engine holding one second of audio at `sample_rate`."""
    return FakeTtsEngine(
        make_model_info(id=MODEL_ID),
        sample_rate=sample_rate,
        samples_per_sentence=sample_rate,
        **kwargs,
    )


def make_handler(
    client,
    *,
    storage=None,
    engine=None,
    streaming=True,
    development=True,
):
    """Return a handler wired to `client`, synthesizing through a Hub over fakes."""
    storage = storage if storage is not None else make_storage()
    engine = engine if engine is not None else make_engine()
    hub = make_hub(
        engine=engine,
        storage=storage,
        middlewares=[ResolveLanguageMiddleware().invoke],
        frame_duration=FRAME_DURATION_MS,
    )

    return TtsEngineHubEventHandler(
        hub,
        storage,
        SERVICE_NAME,
        supports_synthesize_streaming=streaming,
        throw_detailed_errors=development,
        reader=client.reader,
        writer=client.writer,
    )


def synthesize_event(text="hello", voice_id=VOICE_ID, text_format=None):
    return Synthesize(
        text=text,
        voice=SynthesizeVoice(name=voice_id) if voice_id is not None else None,
        text_format=text_format,
    ).event()


def start_event(voice_id=VOICE_ID, text_format=None):
    return SynthesizeStart(
        voice=SynthesizeVoice(name=voice_id) if voice_id is not None else None,
        text_format=text_format,
    ).event()


def synthesize_event_with_language(text="hello", voice_id=VOICE_ID, language=OTHER_LANGUAGE):
    """A synthesize event carrying a Language beside the Voice name.

    Built as a raw payload on purpose: `SynthesizeVoice.to_dict` drops the Language
    whenever a name is present, so the dataclass cannot express what a real client
    sends.
    """
    return Event(
        type="synthesize", data={"text": text, "voice": {"name": voice_id, "language": language}}
    )


def start_event_with_language(voice_id=VOICE_ID, language=OTHER_LANGUAGE):
    """A synthesize-start event carrying a Language beside the Voice name, as a raw payload."""
    return Event(type="synthesize-start", data={"voice": {"name": voice_id, "language": language}})


def parsed_audio(event):
    """Parse an `audio-start` or `audio-chunk` event as its Wyoming audio event."""
    if AudioStart.is_type(event.type):
        return AudioStart.from_event(event)

    return AudioChunk.from_event(event)


def audio_start_and_chunk_events(events):
    """The audio-start and audio-chunk events in a response."""
    return [
        event
        for event in events
        if AudioStart.is_type(event.type) or AudioChunk.is_type(event.type)
    ]


class RecordingHandler:
    """A handler that keeps the events it wrote, so a test can read their payloads.

    A client parses events back off the wire, which turns every payload into bytes and
    hides what the handler actually handed to the writer.
    """

    def __init__(self, handler):
        self._handler = handler
        self._send = handler.write_event
        self.written: list[Event] = []
        handler.write_event = self._write

    async def _write(self, event):
        self.written.append(event)
        await self._send(event)

    async def handle_event(self, event):
        return await self._handler.handle_event(event)


class TestDescribe:
    """A Describe request is answered with one program advertising the Active Models' Voices."""

    async def test_answered_with_one_program_named_after_the_service(self):
        client = WyomingClient()

        events = await client.send(make_handler(client), Describe().event())

        programs = Info.from_event(events[0]).tts
        assert len(programs) == 1
        assert programs[0].name == SERVICE_NAME

    async def test_advertises_only_active_models_voices_sorted_by_name(self):
        client = WyomingClient()

        events = await client.send(make_handler(client), Describe().event())

        voices = Info.from_event(events[0]).tts[0].voices
        assert [voice.name for voice in voices] == [f"{MODEL_ID}-aidar", f"{MODEL_ID}-zebra"]

    async def test_the_description_is_what_the_package_says_the_project_is(self):
        """The description is the package summary, not something restated beside it.

        They were one string read twice; restating it would let the two drift, and the
        client only ever sees this one.
        """
        client = WyomingClient()

        events = await client.send(make_handler(client), Describe().event())

        assert Info.from_event(events[0]).tts[0].description == __metadata__["summary"]

    async def test_the_description_names_a_tts_engine_hub(self):
        """A client reading this is told what the project is, not what it started as."""
        client = WyomingClient()

        events = await client.send(make_handler(client), Describe().event())

        assert "TTS Engine Hub" in Info.from_event(events[0]).tts[0].description

    async def test_the_attribution_names_the_project(self):
        """Credit goes to the project, not to the service name or the distribution.

        Both are the strings this used to be credited under: the distribution is named
        after one engine family, and the service name is whatever the operator called
        this deployment. Renaming a service to something of one's own must not make the
        server claim the credit for it.
        """
        client = WyomingClient()

        events = await client.send(make_handler(client), Describe().event())

        attribution = Info.from_event(events[0]).tts[0].attribution
        assert attribution.name == PROJECT_NAME
        assert attribution.name != SERVICE_NAME
        assert attribution.name != __metadata__["name"]

    @pytest.mark.parametrize("engine_type", list(EngineType))
    async def test_a_voice_is_credited_to_the_engine_family_that_built_it(self, engine_type):
        """Both halves of the credit: which family, and where to find it.

        Parametrised over every family rather than checked once for Silero, because a
        hardcoded pair naming one engine satisfies any test that only asks about that
        engine — which is exactly what was advertised before.
        """
        client = WyomingClient()
        storage = YamlDataStorage(
            PredefinedData(
                models=[make_model_info(id=MODEL_ID, engine_type=engine_type, languages=["ru"])],
                voices=[make_voice(voice_id=f"{MODEL_ID}-aidar", name="aidar", model=MODEL_ID)],
            ),
            active_models=[MODEL_ID],
        )

        events = await client.send(make_handler(client, storage=storage), Describe().event())

        attribution = Info.from_event(events[0]).tts[0].voices[0].attribution
        assert attribution.name == engine_type.value
        assert attribution.url == ENGINE_REPO_URLS[engine_type]

    async def test_two_engine_families_are_credited_differently(self):
        """The credit follows the Model Info the Voice belongs to, not the server's."""
        client = WyomingClient()
        storage = YamlDataStorage(
            PredefinedData(
                models=[
                    make_model_info(id=MODEL_ID, engine_type=EngineType.SILERO, languages=["ru"]),
                    make_model_info(
                        id=OTHER_MODEL_ID, engine_type=EngineType.QWEN3, languages=["en"]
                    ),
                ],
                voices=[
                    make_voice(voice_id=f"{MODEL_ID}-aidar", name="aidar", model=MODEL_ID),
                    make_voice(
                        voice_id=f"{OTHER_MODEL_ID}-vivian", name="vivian", model=OTHER_MODEL_ID
                    ),
                ],
            ),
            active_models=[MODEL_ID, OTHER_MODEL_ID],
        )

        events = await client.send(make_handler(client, storage=storage), Describe().event())

        credits = {
            voice.name: (voice.attribution.name, voice.attribution.url)
            for voice in Info.from_event(events[0]).tts[0].voices
        }
        assert credits == {
            f"{MODEL_ID}-aidar": ("silero", ENGINE_REPO_URLS[EngineType.SILERO]),
            f"{OTHER_MODEL_ID}-vivian": ("qwen3", ENGINE_REPO_URLS[EngineType.QWEN3]),
        }

    async def test_a_voice_whose_model_info_is_gone_is_refused_by_name(self):
        """A Voice cannot be advertised without the Model Info that gives it meaning.

        Its Languages and its TTS Engine both come from that Model Info, so there is no
        Voice to describe — and describing it as one engine's would be the guess this
        attribution just stopped making.
        """
        client = WyomingClient()
        storage = FakeDataStorage(
            models=[make_model_info(id=MODEL_ID)],
            voices=[
                make_voice(voice_id=f"{OTHER_MODEL_ID}-en_0", name="en_0", model=OTHER_MODEL_ID)
            ],
        )

        events = await client.send(make_handler(client, storage=storage), Describe().event())

        assert f"{OTHER_MODEL_ID}-en_0" in Error.from_event(events[0]).text

    async def test_naming_the_service_does_not_change_the_credit(self):
        """The two names are decided apart, so neither can become the other."""
        client = WyomingClient()
        handler = make_handler(client)

        renamed = await client.send(handler, Describe().event())
        client.written_events()
        handler._wyoming_service_name = "Kitchen Speaker"
        after_renaming = await client.send(handler, Describe().event())

        program = Info.from_event(after_renaming[0]).tts[0]
        assert program.name == "Kitchen Speaker"
        assert program.attribution.name == Info.from_event(renamed[0]).tts[0].attribution.name

    async def test_each_voice_reports_its_model_info_languages(self):
        client = WyomingClient()
        handler = make_handler(client, storage=make_storage(languages=("ru", "en-GB")))

        events = await client.send(handler, Describe().event())

        voices = Info.from_event(events[0]).tts[0].voices
        assert [voice.languages for voice in voices] == [["ru", "en-GB"], ["ru", "en-GB"]]


class TestSynthesize:
    """A Synthesize request is answered with audio: one start, its chunks, one stop."""

    async def test_emits_audio_start_then_chunks_then_audio_stop(self):
        client = WyomingClient()
        engine = make_engine()

        events = await client.send(make_handler(client, engine=engine), synthesize_event())

        assert events[0].type == "audio-start"
        assert events[-1].type == "audio-stop"
        assert len(streamed_audio_bytes(events)) == engine.audio_size_bytes

    async def test_announces_the_format_the_chunk_declares(self):
        client = WyomingClient()
        engine = make_engine(bytes_per_sample=4, channels=2)

        events = await client.send(make_handler(client, engine=engine), synthesize_event())

        expected = (engine.sample_rate, engine.bytes_per_sample, engine.channels)
        assert announced_audio_format(events) == expected
        assert audio_formats(events) == {expected}
        assert len(streamed_audio_bytes(events)) == engine.audio_size_bytes

    async def test_audio_start_is_emitted_once_however_many_chunks_follow(self):
        client = WyomingClient()

        events = await client.send(make_handler(client), synthesize_event())

        starts = [event for event in events if AudioStart.is_type(event.type)]
        assert len(starts) == 1
        assert len(audio_start_and_chunk_events(events)) == CHUNK_EVENTS_PER_REQUEST + 1

    async def test_every_audio_event_agrees_on_rate_width_and_channels(self):
        client = WyomingClient()

        events = await client.send(make_handler(client), synthesize_event())

        audio = audio_start_and_chunk_events(events)
        assert audio, "expected audio events"
        for event in audio:
            parsed = parsed_audio(event)
            assert (parsed.rate, parsed.width, parsed.channels) == (SAMPLE_RATE, 2, 1)

    async def test_audio_bytes_are_the_engines_audio_byte_for_byte(self):
        """The bytes a client receives are the audio the TTS Engine produced, unchanged.

        The Engine is asked for strided audio, so the frames the Hub streams are views
        of it and the Wyoming handler is the one place that audio becomes bytes.
        """
        samples = 64
        client = WyomingClient()
        engine = FakeTtsEngine(
            make_model_info(id=MODEL_ID),
            sample_rate=SAMPLE_RATE,
            samples_per_sentence=samples,
            strided_audio=True,
        )

        events = await client.send(make_handler(client, engine=engine), synthesize_event())

        assert (
            streamed_audio_bytes(events)
            == sample_index_audio(samples, engine.sample_dtype).tobytes()
        )

    async def test_audio_reaches_the_wire_as_a_byte_view_of_the_engines_buffer(self):
        """Each Frame is written as one byte view over the audio the TTS Engine produced.

        Wyoming announces a payload's length before writing the payload, so a Frame has
        to be addressed a byte at a time for the announced length to be the number of
        bytes that follow it. A view of the samples would announce its length in samples.
        """
        client = WyomingClient()
        engine = make_engine()
        handler = RecordingHandler(make_handler(client, engine=engine))

        await client.send(handler, synthesize_event())

        payloads = [event.payload for event in handler.written if AudioChunk.is_type(event.type)]
        assert payloads, "expected audio chunks to be written"
        for payload in payloads:
            assert isinstance(payload, memoryview)
            assert payload.format == "B", "the announced length must count bytes, not samples"
            assert payload.obj.dtype == engine.sample_dtype, "a re-typed copy, not the audio"
            assert np.shares_memory(payload.obj, engine.emitted_audio[0]), "a Frame must not copy"

        assert sum(len(payload) for payload in payloads) == engine.audio_size_bytes


class TestRejections:
    """A request the server cannot serve is answered with an error, and no audio."""

    @pytest.mark.parametrize(
        ("event", "expected_text"),
        [
            pytest.param(synthesize_event(text=""), "Text is empty", id="empty-text"),
            pytest.param(synthesize_event(text="   "), "Text is empty", id="whitespace-text"),
            pytest.param(synthesize_event(voice_id=None), "No voice", id="no-voice"),
            pytest.param(
                synthesize_event(voice_id="nobody"), "Unsupported voice", id="unknown-voice"
            ),
            pytest.param(
                synthesize_event(text_format="markdown"),
                "Unsupported text format",
                id="unknown-text-format",
            ),
        ],
    )
    async def test_rejected_request_answers_with_an_error_and_no_audio(self, event, expected_text):
        client = WyomingClient()

        events = await client.send(make_handler(client), event)

        assert [event.type for event in events] == ["error"]
        assert expected_text in Error.from_event(events[0]).text

    @pytest.mark.parametrize(
        ("text_format", "ssml_supported"),
        [
            pytest.param(SynthesizeTextFormat.TEXT, False, id="text"),
            pytest.param(SynthesizeTextFormat.SSML, True, id="ssml"),
        ],
    )
    async def test_accepted_request_answers_with_audio(self, text_format, ssml_supported):
        """The guard rejects only what it should: a request in a known Text Format gets audio.

        SSML reaches a Model Info that declares support for it; plain text needs no
        declaration, so it is asked of a Model Info that declares none.
        """
        client = WyomingClient()

        events = await client.send(
            make_handler(client, storage=make_storage(ssml_supported=ssml_supported)),
            synthesize_event(text_format=text_format),
        )

        assert events[0].type == "audio-start"

    async def test_ssml_a_model_info_does_not_declare_is_answered_with_an_error(self):
        """SSML asked of a Model Info that does not declare it never becomes audio."""
        client = WyomingClient()

        events = await client.send(
            make_handler(client, storage=make_storage(ssml_supported=False)),
            synthesize_event(text_format=SynthesizeTextFormat.SSML),
        )

        assert [event.type for event in events] == ["error"]
        message = Error.from_event(events[0]).text
        assert "ssml" in message.lower(), "the error must name the Text Format"
        assert MODEL_ID in message, "the error must name the Model Info"


class TestAudioWithNoSampleAxis:
    """Audio that cannot be framed is refused before a client is told anything about it."""

    async def test_audio_with_no_sample_axis_is_never_streamed(self):
        """A Chunk the TTS Engine cannot frame is answered with an error, not with audio."""
        client = WyomingClient()
        engine = NoSampleAxisTtsEngine(make_model_info(id=MODEL_ID))

        events = await client.send(make_handler(client, engine=engine), synthesize_event())

        assert audio_start_and_chunk_events(events) == []
        assert Error.is_type(events[0].type)


class TestErrorDetail:
    """A failure inside synthesis is reported to the client without leaking internals."""

    async def test_production_mode_reports_a_generic_internal_error(self):
        client = WyomingClient()
        handler = make_handler(
            client, engine=ExplodingTtsEngine(make_model_info(id=MODEL_ID)), development=False
        )

        events = await client.send(handler, synthesize_event())

        assert [event.type for event in events] == ["error"]
        error = Error.from_event(events[0])
        assert error.text == "Internal Server Error"
        assert FAILURE not in error.text

    async def test_development_mode_includes_the_underlying_message(self):
        client = WyomingClient()
        handler = make_handler(
            client, engine=ExplodingTtsEngine(make_model_info(id=MODEL_ID)), development=True
        )

        events = await client.send(handler, synthesize_event())

        error = Error.from_event(events[0])
        assert error.text != "Internal Server Error"
        assert "Sentence inference error" in error.text


class TestLanguageFromTheWire:
    """A Language the client sends beside the Voice reaches the Model Info that serves it."""

    async def test_language_beside_the_voice_name_reaches_the_engine(self):
        """A Language on the wire is what the engine is asked to speak.

        The request is built from a raw event payload because the `wyoming` library
        discards `SynthesizeVoice.language` once a name is present.
        """
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(
            client, engine=engine, storage=make_storage(languages=(LANGUAGE, OTHER_LANGUAGE))
        )

        events = await client.send(handler, synthesize_event_with_language())

        assert events[0].type == "audio-start"
        assert engine.languages == [OTHER_LANGUAGE]

    async def test_request_without_a_language_synthesizes_in_the_model_info_language(self):
        """A request naming only a Voice is served in the Model Info's declared Language."""
        client = WyomingClient()
        engine = make_engine()

        events = await client.send(make_handler(client, engine=engine), synthesize_event())

        assert events[0].type == "audio-start"
        assert engine.languages == [LANGUAGE]

    async def test_language_the_model_info_does_not_declare_is_answered_with_an_error(self):
        """A Language the Model Info cannot speak is refused to the client, with no audio."""
        client = WyomingClient()
        engine = make_engine()

        events = await client.send(
            make_handler(client, engine=engine),
            synthesize_event_with_language(language="fr"),
        )

        assert [event.type for event in events] == ["error"]
        assert engine.synthesized_texts == []


class TestStreaming:
    """Streaming requests are served as text arrives, and ignored when disabled."""

    async def test_each_chunk_is_streamed_as_it_arrives_and_the_stop_is_confirmed(self):
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(client, engine=engine, streaming=True)

        first = await client.send(handler, start_event())
        assert first == []

        streamed = await client.send(handler, SynthesizeChunk(text="hello").event())
        assert [event.type for event in streamed] == [
            "audio-start",
            *(["audio-chunk"] * CHUNK_EVENTS_PER_REQUEST),
            "audio-stop",
        ]

        # The second chunk's audio arrives before the stop, rather than being held
        # back until the whole stream ends.
        second = await client.send(handler, SynthesizeChunk(text="goodbye").event())
        assert [event.type for event in second] == [
            "audio-start",
            *(["audio-chunk"] * CHUNK_EVENTS_PER_REQUEST),
            "audio-stop",
        ]

        stopped = await client.send(handler, SynthesizeStop().event())
        assert [event.type for event in stopped] == [SynthesizeStopped().event().type]
        assert engine.synthesized_texts == ["hello", "goodbye"]

    @pytest.mark.parametrize(
        ("start", "chunk_text", "expected_text"),
        [
            pytest.param(start_event(), "   ", "Text is empty", id="empty-text"),
            pytest.param(start_event(voice_id=None), "hello", "No voice", id="no-voice"),
            pytest.param(
                start_event(voice_id="nobody"), "hello", "Unsupported voice", id="unknown-voice"
            ),
            pytest.param(
                start_event(text_format="markdown"),
                "hello",
                "Unsupported text format",
                id="unknown-text-format",
            ),
            pytest.param(
                start_event(text_format=SynthesizeTextFormat.SSML),
                "hello",
                "does not accept SSML",
                id="ssml-not-declared",
            ),
        ],
    )
    async def test_rejected_chunk_answers_with_an_error_and_no_audio(
        self, start, chunk_text, expected_text
    ):
        """The streaming path applies the same guards as a whole request."""
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(client, engine=engine, streaming=True)

        await client.send(handler, start)
        events = await client.send(handler, SynthesizeChunk(text=chunk_text).event())

        assert [event.type for event in events] == ["error"]
        assert expected_text in Error.from_event(events[0]).text
        assert engine.synthesized_texts == []

    async def test_stop_without_a_chunk_still_confirms_the_stop(self):
        client = WyomingClient()
        handler = make_handler(client, streaming=True)

        await client.send(handler, start_event())
        stopped = await client.send(handler, SynthesizeStop().event())

        assert [event.type for event in stopped] == [SynthesizeStopped().event().type]

    async def test_language_from_the_start_event_reaches_every_chunk(self):
        """The Language named at the start of a stream speaks for the whole stream."""
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(
            client, engine=engine, storage=make_storage(languages=(LANGUAGE, OTHER_LANGUAGE))
        )

        await client.send(handler, start_event_with_language())
        await client.send(handler, SynthesizeChunk(text="hello").event())
        await client.send(handler, SynthesizeChunk(text="goodbye").event())
        await client.send(handler, SynthesizeStop().event())

        assert engine.languages == [OTHER_LANGUAGE, OTHER_LANGUAGE]

    async def test_language_from_a_finished_stream_does_not_leak_into_the_next(self):
        """The stream's Language is forgotten at the stop, so the next stream resolves afresh."""
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(
            client, engine=engine, storage=make_storage(languages=(LANGUAGE, OTHER_LANGUAGE))
        )

        await client.send(handler, start_event_with_language())
        await client.send(handler, SynthesizeChunk(text="hello").event())
        await client.send(handler, SynthesizeStop().event())

        # A stream naming no Language has nothing to resolve from, and a stale
        # Language from the finished stream would paper over that by synthesizing.
        await client.send(handler, start_event())
        events = await client.send(handler, SynthesizeChunk(text="goodbye").event())
        await client.send(handler, SynthesizeStop().event())

        assert [event.type for event in events] == ["error"]
        assert engine.languages == [OTHER_LANGUAGE]

    async def test_whole_request_synthesize_is_ignored_mid_stream(self):
        """A Synthesize arriving mid-stream is a compatibility no-op: the chunk
        events carry the text. Pinned as current behaviour, not from the ticket."""
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(client, engine=engine, streaming=True)

        await client.send(handler, start_event())
        events = await client.send(handler, synthesize_event())

        assert events == []
        assert engine.synthesized_texts == []

    async def test_streaming_disabled_ignores_the_streaming_events(self):
        client = WyomingClient()
        handler = make_handler(client, streaming=False)

        events = await client.send(
            handler,
            start_event(),
            SynthesizeChunk(text="hello").event(),
            SynthesizeStop().event(),
        )

        assert events == []

    async def test_streaming_disabled_still_serves_a_whole_request_synthesize(self):
        client = WyomingClient()
        engine = make_engine()
        handler = make_handler(client, engine=engine, streaming=False)

        events = await client.send(handler, synthesize_event())

        assert events[0].type == "audio-start"
        assert engine.synthesized_texts == ["hello"]
