import pytest

from benchmark_sample import (
    SAMPLE_TEXT,
    CountingTtsEngine,
    SentenceRecorder,
    SynthesisMeasurement,
    audio_duration_seconds,
    default_text_for,
    peak_memory_report,
    real_time_factor,
)
from src.config import Settings
from src.tts.data_storage import YamlDataStorage
from src.tts.middleware import ResolveLanguageMiddleware, SplitSentencesMiddleware
from src.tts.models import PredefinedData
from src.tts.preprocessing import TextSentenizerFactory
from tests.helpers import (
    FakeEngineManager,
    FakeTtsEngine,
    collect_hub_sentences,
    make_hub,
    make_model_info,
    make_voice,
)

BYTES_PER_SAMPLE = 2
CHANNELS = 1
SAMPLE_RATE = 24000


class TestAudioDuration:
    def test_audio_bytes_are_measured_as_seconds_of_audio(self):
        """A second of 16-bit mono audio at the sample rate is one second long."""
        audio_bytes = BYTES_PER_SAMPLE * CHANNELS * SAMPLE_RATE

        assert audio_duration_seconds(
            audio_bytes,
            bytes_per_sample=BYTES_PER_SAMPLE,
            channels=CHANNELS,
            sample_rate=SAMPLE_RATE,
        ) == pytest.approx(1.0)

    def test_channels_and_sample_width_are_both_divided_out(self):
        """Stereo 32-bit audio holds two samples per frame for twice the width."""
        stereo_seconds = audio_duration_seconds(
            4 * 2 * SAMPLE_RATE,
            bytes_per_sample=4,
            channels=2,
            sample_rate=SAMPLE_RATE,
        )

        assert stereo_seconds == pytest.approx(1.0)

    @pytest.mark.parametrize(
        ("audio_bytes", "sample_rate"),
        [
            pytest.param(0, SAMPLE_RATE, id="no-audio"),
            pytest.param(BYTES_PER_SAMPLE * SAMPLE_RATE, 0, id="no-sample-rate"),
        ],
    )
    def test_nothing_to_measure_is_no_audio(self, audio_bytes, sample_rate):
        """A Frame that carries nothing, or a format with no rate, is not a duration."""
        assert (
            audio_duration_seconds(
                audio_bytes,
                bytes_per_sample=BYTES_PER_SAMPLE,
                channels=CHANNELS,
                sample_rate=sample_rate,
            )
            == 0.0
        )


class TestRealTimeFactor:
    def test_speaking_faster_than_real_time_is_below_one(self):
        """Half the wall time for a second of audio is half a second per second."""
        assert real_time_factor(0.5, 1.0) == pytest.approx(0.5)

    def test_no_audio_yields_no_ratio(self):
        """A request that produced nothing has no speed to report."""
        assert real_time_factor(3.0, 0.0) == 0.0


class TestReport:
    def test_report_counts_sentences_chunks_and_frames_separately(self):
        """The three counts are different units, so all three are reported."""
        measurement = SynthesisMeasurement(
            sentences=2, chunks=3, frames=40, audio_seconds=2.0, wall_seconds=1.0
        )

        report = measurement.report()

        assert "Sentences:        2" in report
        assert "Chunks:           3" in report
        assert "Frames:           40" in report
        assert "FASTER THAN REAL TIME" in report

    def test_a_request_slower_than_its_own_audio_says_so(self):
        """A ratio above 1.0 is slower than real time, and the report must not claim otherwise."""
        report = SynthesisMeasurement(audio_seconds=1.0, wall_seconds=2.0).report()

        assert "SLOWER THAN REAL TIME" in report

    def test_a_request_that_produced_no_audio_reports_no_first_frame(self):
        """Nothing arriving is not the same as arriving instantly."""
        report = SynthesisMeasurement().report()

        assert "First Frame:      N/A" in report


class TestPeakMemory:
    def test_a_device_that_declared_nothing_falls_back_to_process_memory(self):
        """With no device counter to read, the process high-water mark is used instead."""
        peak_memory_mb, source = peak_memory_report(None)

        assert peak_memory_mb > 0
        assert source == "process peak RSS, lifetime", "a lifetime figure must say so"

    def test_a_measurement_with_no_peak_memory_reports_it_as_unmeasured(self):
        """An unmeasured figure is not a zero."""
        assert "Peak memory:      N/A" in SynthesisMeasurement().report()


class TestSampleText:
    @pytest.mark.parametrize("language", sorted(SAMPLE_TEXT))
    def test_every_sample_is_long_enough_to_be_split(self, language):
        """One Sentence would measure a single inference, so every sample must be longer.

        Measured against the configured limit, so the samples cannot quietly fall below
        it if the default changes.
        """
        assert len(SAMPLE_TEXT[language]) > Settings().max_sentence_chars

    def test_sample_text_comes_from_the_language_asked_for(self):
        """A Model Info can only be asked to speak the Languages it declares."""
        assert default_text_for("ru") == SAMPLE_TEXT["ru"]
        assert default_text_for("en") == SAMPLE_TEXT["en"]

    @pytest.mark.parametrize("language", [None, "", "de"])
    def test_an_unknown_language_falls_back_to_english(self, language):
        """A Voice with no declared Language still gets sample text to speak."""
        assert default_text_for(language) == SAMPLE_TEXT["en"]


MODEL_ID = "bench_model"
VOICE_ID = f"{MODEL_ID}-aidar"
# Short enough that this limit splits the text below into two Sentences.
MAX_SENTENCE_CHARS = 30
TWO_SENTENCES = "Hello there. This is a second sentence."


def make_counting_stack():
    """One Model Info, a splitting middleware, a Sentence recorder, and a counting engine."""
    storage = YamlDataStorage(
        PredefinedData(
            models=[make_model_info(id=MODEL_ID, languages=["en"])],
            voices=[make_voice(voice_id=VOICE_ID, name="aidar", model=MODEL_ID)],
        )
    )
    engine = CountingTtsEngine(FakeTtsEngine(make_model_info(id=MODEL_ID)))
    recorder = SentenceRecorder()
    hub = make_hub(
        engine=engine,
        middlewares=[
            ResolveLanguageMiddleware().invoke,
            SplitSentencesMiddleware(
                max_sentence_chars=MAX_SENTENCE_CHARS,
                text_sentenizer_factory=TextSentenizerFactory(),
            ).invoke,
            recorder,
        ],
        storage=storage,
        engine_manager=FakeEngineManager({MODEL_ID: engine}),
    )

    return hub, engine, recorder


class TestCounters:
    """The three counts come from three different places in the pipeline."""

    async def test_sentences_are_what_the_pipeline_hands_to_synthesis(self):
        """The recorder sees the Sentences after splitting, not the raw input."""
        hub, _, recorder = make_counting_stack()

        await collect_hub_sentences(hub, TWO_SENTENCES, VOICE_ID)

        assert recorder.sentences == ["Hello there.", "This is a second sentence."]

    async def test_chunks_are_counted_on_the_engine_that_yields_them(self):
        """A Chunk is engine output, so it is counted before the Hub frames anything."""
        hub, engine, recorder = make_counting_stack()

        await collect_hub_sentences(hub, TWO_SENTENCES, VOICE_ID)

        assert len(recorder.sentences) == 2, "the text is two Sentences to synthesize"
        assert engine.chunks == len(recorder.sentences), "this engine yields one Chunk per Sentence"

    async def test_frames_are_more_numerous_than_chunks(self):
        """A Chunk is streamed as several Frames, so the two counts cannot be the same."""
        hub, engine, _ = make_counting_stack()

        frames = await collect_hub_sentences(hub, TWO_SENTENCES, VOICE_ID)

        assert len(frames) > engine.chunks, "each Chunk should reach the client as many Frames"
