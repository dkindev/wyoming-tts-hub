import re

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
from src.tts.engine import SileroTTSEngine
from src.tts.models import TextFormat


def _get_language_from_locale_string(locale_str: str) -> str | None:
    if not locale_str:
        return None
    parts = re.split(r"[_.-]", locale_str)
    return parts[0] if parts else None


def _create_wyoming_info(engine: SileroTTSEngine, service_name: str, streaming: bool) -> Info:
    storage = engine.get_storage()
    voices = []
    for voice in storage.get_voices():
        voices.append(
            TtsVoice(
                name=voice.id,
                description=voice.name,
                attribution=Attribution(
                    name="silero",
                    url="https://github.com/snakers4/silero-models",
                ),
                installed=True,
                languages=[_get_language_from_locale_string(voice.locale)],
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


class SileroEventHandler(AsyncEventHandler):
    def __init__(
        self,
        engine: SileroTTSEngine,
        wyoming_service_name: str,
        supports_synthesize_streaming: bool,
        throw_detailed_errors: bool,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._engine = engine
        self._wyoming_service_name = wyoming_service_name
        self._supports_synthesize_streaming = supports_synthesize_streaming
        self._throw_detailed_errors = throw_detailed_errors
        self._is_streaming: bool = False
        self._synthesize: Synthesize | None = None

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
        state = await self._synthesize_pcm_chunks(synthesize)
        return state

    async def _handle_synthesize_start(self, event: Event) -> bool:
        stream_start = SynthesizeStart.from_event(event)
        self._is_streaming = True
        self._synthesize = Synthesize(
            text="", voice=stream_start.voice, text_format=stream_start.text_format
        )
        logger.debug("Text stream started: voice='{voice}'", voice=stream_start.voice)
        return True

    async def _handle_synthesize_chunk(self, event: Event) -> bool:
        assert self._synthesize is not None
        stream_chunk = SynthesizeChunk.from_event(event)
        self._synthesize.text = stream_chunk.text
        state = await self._synthesize_pcm_chunks(self._synthesize)
        logger.debug("Text stream processed.")
        return state

    async def _handle_synthesize_stop(self, event: Event) -> bool:
        assert self._synthesize is not None
        await self.write_event(SynthesizeStopped().event())
        self._is_streaming = False
        self._synthesize = None
        logger.debug("Text stream stopped")
        return True

    async def _handle_describe(self, event: Event) -> bool:
        wyoming_info_event = _create_wyoming_info(
            self._engine, self._wyoming_service_name, self._supports_synthesize_streaming
        ).event()
        await self.write_event(wyoming_info_event)
        return True

    async def _synthesize_pcm_chunks(self, synthesize: Synthesize) -> bool:
        text = synthesize.text.strip()
        if not text:
            await self.write_event(Error(text="Text is empty or whitespace").event())
            return True

        voice_id = synthesize.voice.name if synthesize.voice else None
        if not voice_id:
            await self.write_event(Error(text="No voice specified in Synthesize event").event())
            return True

        if not self._engine.get_storage().get_voice(voice_id):
            await self.write_event(Error(text=f"Unsupported voice: {voice_id}").event())
            return True

        text_format = self._parse_text_format(synthesize)
        if text_format is None:
            await self.write_event(
                Error(text=f"Unsupported text format: {synthesize.text_format}").event()
            )
            return True

        send_start = True
        async for chunk in self._engine.synthesize_pcm_chunks(text, voice_id, text_format):
            if send_start:
                await self.write_event(
                    AudioStart(
                        rate=chunk.sample_rate,
                        width=chunk.bytes_per_sample,
                        channels=chunk.channels,
                    ).event()
                )
                send_start = False

            await self.write_event(
                AudioChunk(
                    rate=chunk.sample_rate,
                    width=chunk.bytes_per_sample,
                    channels=chunk.channels,
                    audio=chunk.audio,
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

        supported_formats = [
            supported_format.value for supported_format in self._engine.get_supported_text_formats()
        ]

        if req_text_format in supported_formats:
            return TextFormat(req_text_format)

        return None
