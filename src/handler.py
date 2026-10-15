from loguru import logger
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeTextFormat,
)

from src import __metadata__, __project_urls__
from src.tts.data_storage import DataStorage
from src.tts.engine_hub import TtsEngineHub
from src.tts.models import TextFormat


def _create_wyoming_info(data_storage: DataStorage, service_name: str, streaming: bool) -> Info:
    voices = []
    for voice in data_storage.get_voices():
        model = data_storage.get_model(voice.model_id)

        voices.append(
            TtsVoice(
                name=voice.id,
                description=voice.name,
                attribution=Attribution(
                    name="silero",
                    url="https://github.com/snakers4/silero-models",
                ),
                installed=True,
                languages=model.languages,
                version=None,
            )
        )

    voices.sort(key=lambda v: v.name)

    return Info(
        tts=[
            TtsProgram(
                name=service_name,
                description=__metadata__["summary"],
                attribution=Attribution(
                    name=__metadata__["name"],
                    url=__project_urls__["Homepage"],
                ),
                installed=True,
                voices=voices,
                supports_synthesize_streaming=streaming,
                version=__metadata__["version"],
            )
        ],
    )


def _language_from_voice(event: Event) -> str | None:
    """Return the Language a client sent beside the Voice, if any.

    Read from the raw event payload rather than the parsed dataclass: the `wyoming`
    library drops `SynthesizeVoice.language` whenever `name` is present, so a Voice
    named on the wire and a Language beside it never both survive parsing.
    """
    voice = event.data.get("voice")
    if not isinstance(voice, dict):
        return None

    language = voice.get("language")
    return language if isinstance(language, str) else None


class TtsEngineHubEventHandler(AsyncEventHandler):
    def __init__(
        self,
        engine: TtsEngineHub,
        data_storage: DataStorage,
        wyoming_service_name: str,
        supports_synthesize_streaming: bool,
        throw_detailed_errors: bool,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._engine = engine
        self._data_storage = data_storage
        self._wyoming_service_name = wyoming_service_name
        self._supports_synthesize_streaming = supports_synthesize_streaming
        self._throw_detailed_errors = throw_detailed_errors
        self._is_streaming: bool = False
        self._synthesize: Synthesize | None = None
        self._language: str | None = None

    async def handle_event(self, event: Event) -> bool:
        try:
            logger.info("Handle '{event_type}'", event_type=event.type)
            logger.debug("Event: {event}", event=event)

            if Describe.is_type(event.type):
                return await self._handle_describe(event)

            if Synthesize.is_type(event.type):
                if self._is_streaming:
                    # Ignore since this is only sent for compatibility reasons.
                    # For streaming, we expect:
                    # [synthesize-start] -> [synthesize-chunk]+ -> [synthesize]? -> [synthesize-stop]
                    return True

                # Sent outside a stream, so we must process it
                return await self._handle_synthesize(event)

            if not self._supports_synthesize_streaming:
                # Streaming is not enabled
                return True

            if SynthesizeStart.is_type(event.type):
                return await self._handle_synthesize_start(event)

            if SynthesizeChunk.is_type(event.type):
                return await self._handle_synthesize_chunk(event)

            if SynthesizeStop.is_type(event.type):
                return await self._handle_synthesize_stop(event)
        except Exception as err:
            logger.exception(err)

            error = (
                Error(text=str(err), code=err.__class__.__name__)
                if self._throw_detailed_errors
                else Error(text="Internal Server Error")
            )

            await self.write_event(error.event())

        return True

    async def _handle_synthesize(self, event: Event) -> bool:
        synthesize = Synthesize.from_event(event)
        state = await self._synthesize_pcm_chunks(synthesize, _language_from_voice(event))
        return state

    async def _handle_synthesize_start(self, event: Event) -> bool:
        stream_start = SynthesizeStart.from_event(event)
        self._is_streaming = True
        self._synthesize = Synthesize(
            text="", voice=stream_start.voice, text_format=stream_start.text_format
        )
        self._language = _language_from_voice(event)
        logger.debug("Text stream started: voice='{voice}'", voice=stream_start.voice)
        return True

    async def _handle_synthesize_chunk(self, event: Event) -> bool:
        assert self._synthesize is not None
        stream_chunk = SynthesizeChunk.from_event(event)
        self._synthesize.text = stream_chunk.text
        state = await self._synthesize_pcm_chunks(self._synthesize, self._language)
        logger.debug("Text stream processed.")
        return state

    async def _handle_synthesize_stop(self, event: Event) -> bool:
        assert self._synthesize is not None
        await self.write_event(SynthesizeStopped().event())
        self._is_streaming = False
        self._synthesize = None
        self._language = None
        logger.debug("Text stream stopped")
        return True

    async def _handle_describe(self, event: Event) -> bool:
        wyoming_info_event = _create_wyoming_info(
            self._data_storage, self._wyoming_service_name, self._supports_synthesize_streaming
        ).event()
        await self.write_event(wyoming_info_event)
        return True

    async def _synthesize_pcm_chunks(self, synthesize: Synthesize, language: str | None) -> bool:
        text = synthesize.text.strip()
        if not text:
            await self.write_event(Error(text="Text is empty or whitespace").event())
            return True

        voice_id = synthesize.voice.name if synthesize.voice else None
        if not voice_id:
            await self.write_event(Error(text="No voice specified in Synthesize event").event())
            return True

        if not self._data_storage.get_voice(voice_id):
            await self.write_event(Error(text=f"Unsupported voice: {voice_id}").event())
            return True

        text_format = self._parse_text_format(synthesize)
        if text_format is None:
            await self.write_event(
                Error(text=f"Unsupported text format: {synthesize.text_format}").event()
            )
            return True

        send_start = True
        async for chunk in self._engine.synthesize_pcm_chunks(
            text, voice_id, text_format, language
        ):
            if send_start:
                await self.write_event(
                    AudioStart(
                        rate=chunk.sample_rate,
                        width=chunk.bytes_per_sample,
                        channels=chunk.channels,
                    ).event()
                )
                send_start = False

            # A Frame is a view over its Chunk's audio, and Wyoming's writer
            # hands the payload straight to the stream, so a byte view of the frame
            # goes out without being copied. It is cast to bytes because Wyoming
            # announces the payload's length before writing it, and a view of the
            # samples would announce that length in samples. Wyoming annotates its
            # audio event as taking bytes, which is narrower than what its writer
            # accepts.
            await self.write_event(
                AudioChunk(
                    rate=chunk.sample_rate,
                    width=chunk.bytes_per_sample,
                    channels=chunk.channels,
                    audio=memoryview(chunk.audio).cast("B"),  # type: ignore[arg-type]
                ).event()
            )

        await self.write_event(AudioStop().event())

        return True

    def _parse_text_format(self, synthesize: Synthesize) -> TextFormat | None:
        text_format = TextFormat.TEXT

        req_text_format: str | None = (
            synthesize.text_format.value
            if isinstance(synthesize.text_format, SynthesizeTextFormat)
            else synthesize.text_format
        )

        if not req_text_format:
            return text_format

        try:
            return TextFormat(req_text_format)
        except ValueError:
            pass

        return None
