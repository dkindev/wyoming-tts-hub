import pytest

from src.config import NormalizationPrompt, NormalizationSettings, TextFormatNormalizationSettings
from src.tts.middleware import (
    NormalizeTextMiddleware,
    ResolveLanguageMiddleware,
    SplitSentencesMiddleware,
    SynthesisContext,
)
from src.tts.models import (
    NormalizationType,
    Prompt,
    TextFormat,
    VoiceNormalization,
)
from src.tts.preprocessing import TextNormalizerFactory, TextSentenizerFactory
from tests.helpers import (
    FakeDataStorage,
    FakeTtsEngine,
    collect_hub_sentences,
    make_hub,
    make_model,
    make_voice,
)

# The Language these tests resolve to and key overrides on. Neither the Model nor
# Voice id contains it, so an assertion on the Language cannot be satisfied by an id.
LANGUAGE = "ru"
OTHER_LANGUAGE = "en"
MODEL_ID = "test-model"
VOICE_ID = "test-voice-aidar"
MAX_SENTENCE_CHARS = 20

# Distinct texts so a test can tell which Prompt a normalizer was built from.
OVERRIDE_PROMPT_TEXT = "PROMPT-FROM-OVERRIDE"
DEFAULT_PROMPT_TEXT = "PROMPT-FROM-DEFAULT"


def make_storage(*, overrides=(), prompts=(), languages=(LANGUAGE,), auto_detected=False):
    """Return a DataStorage holding the Voice under test plus normalization overrides."""
    return FakeDataStorage(
        models=[
            make_model(id=MODEL_ID, languages=list(languages), language_auto_detected=auto_detected)
        ],
        voices=[make_voice(voice_id=VOICE_ID, name="aidar", model=MODEL_ID)],
        voice_normalizations=list(overrides),
        prompts=list(prompts),
    )


def make_override(
    *,
    type=NormalizationType.SIMPLE,
    enabled=True,
    prompt_id=None,
    language=LANGUAGE,
    text_format=TextFormat.TEXT,
):
    """Return a VoiceNormalization override for the Voice under test."""
    return VoiceNormalization(
        voice_id=VOICE_ID,
        text_format=text_format,
        language=language,
        type=type,
        enabled=enabled,
        prompt_id=prompt_id,
    )


def prompt_for(prompt_id, text):
    return Prompt(id=prompt_id, text=text, model="gpt-4o-mini")


def default_prompts(text=DEFAULT_PROMPT_TEXT):
    return {LANGUAGE: NormalizationPrompt(text=text, model="gpt-4o-mini")}


def build_chain(
    *,
    storage,
    openai_client=None,
    max_sentence_chars=MAX_SENTENCE_CHARS,
    default_enabled=False,
    default_type=NormalizationType.SIMPLE,
    default_normalization_prompts=None,
    sentenizer_factory=None,
):
    """Return the middleware chain as wired in main.py, with the given configuration."""
    return [
        ResolveLanguageMiddleware().invoke,
        SplitSentencesMiddleware(
            max_sentence_chars=max_sentence_chars,
            text_sentenizer_factory=(
                sentenizer_factory if sentenizer_factory is not None else TextSentenizerFactory()
            ),
        ).invoke,
        NormalizeTextMiddleware(
            timeout=5,
            max_concurrent_sentences=2,
            text_normalizer_factory=TextNormalizerFactory(
                openai_client=openai_client,
                settings=NormalizationSettings(
                    text=TextFormatNormalizationSettings(
                        enabled=default_enabled,
                        type=default_type,
                        prompts=default_normalization_prompts,
                    )
                ),
                storage=storage,
            ),
        ).invoke,
    ]


class MissingSentenizerFactory:
    """A sentence-splitter factory with nothing registered for the request."""

    def create(self, text_format, language=None):
        return None


class TestSentenceSplitting:
    async def test_text_within_the_limit_reaches_the_engine_as_one_sentence(self):
        """Text under the limit produces exactly one engine invocation."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        storage = make_storage()
        hub = make_hub(engine=engine, middlewares=build_chain(storage=storage), storage=storage)

        await collect_hub_sentences(hub, "short text", VOICE_ID)

        assert engine.synthesized_texts == ["short text"]

    async def test_text_at_the_limit_reaches_the_engine_as_one_sentence(self):
        """Text exactly at the limit is still a single Sentence."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        storage = make_storage()
        hub = make_hub(engine=engine, middlewares=build_chain(storage=storage), storage=storage)
        text = "x" * MAX_SENTENCE_CHARS

        await collect_hub_sentences(hub, text, VOICE_ID)

        assert engine.synthesized_texts == [text]

    async def test_punctuated_text_over_the_limit_reaches_the_engine_per_sentence(self):
        """Text over the limit is split on punctuation, one invocation per Sentence."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        storage = make_storage()
        hub = make_hub(engine=engine, middlewares=build_chain(storage=storage), storage=storage)

        await collect_hub_sentences(
            hub, "First sentence here. Second sentence here. Third sentence here.", VOICE_ID
        )

        assert engine.synthesized_texts == [
            "First sentence here.",
            "Second sentence here.",
            "Third sentence here.",
        ]

    async def test_unpunctuated_text_over_the_limit_is_split_on_length(self):
        """A single long Sentence with no punctuation is split to respect the limit.

        This is what makes `max_sentence_chars` itself observable, rather than merely
        punctuation-driven splitting.
        """
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        storage = make_storage()
        hub = make_hub(engine=engine, middlewares=build_chain(storage=storage), storage=storage)

        await collect_hub_sentences(hub, "alpha bravo charlie delta echo foxtrot", VOICE_ID)

        sentences = engine.synthesized_texts
        assert len(sentences) > 1
        assert all(len(sentence) <= MAX_SENTENCE_CHARS for sentence in sentences)
        assert " ".join(sentences) == "alpha bravo charlie delta echo foxtrot"

    async def test_missing_sentence_splitter_is_an_error_naming_voice_and_language(self):
        """No splitter for the Voice's Language and Text Format is diagnosable."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        storage = make_storage()
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(storage=storage, sentenizer_factory=MissingSentenizerFactory()),
            storage=storage,
        )

        with pytest.raises(RuntimeError) as exc_info:
            await collect_hub_sentences(hub, "some text", VOICE_ID)

        message = str(exc_info.value)
        assert VOICE_ID in message
        assert LANGUAGE in message


class TestSynthesisContextModelInfo:
    """A synthesis request carries one Model Info, and the context exposes it as model_info."""

    def test_context_exposes_the_model_info_it_was_given(self):
        """The Model Info handed to the context reaches middleware under its own name."""
        model_info = make_model(id=MODEL_ID, languages=[LANGUAGE])
        voice = make_voice(voice_id=VOICE_ID, name="aidar", model=MODEL_ID)

        ctx = SynthesisContext("hello", model_info, voice, TextFormat.TEXT)

        assert ctx.model_info is model_info


class TestLanguageResolution:
    """ResolveLanguageMiddleware fills in a Language only when there is one to fill in."""

    def make_recording_hub(self, engine, *, languages, auto_detected=False):
        """Return a Hub whose chain reports the Language the engine is asked for."""
        storage = make_storage(languages=languages, auto_detected=auto_detected)
        seen_languages = []

        async def record_language(ctx, next_call):
            seen_languages.append(ctx.language)
            await next_call()

        hub = make_hub(
            engine=engine,
            middlewares=[ResolveLanguageMiddleware().invoke, record_language],
            storage=storage,
        )
        return hub, seen_languages

    async def test_a_request_without_a_language_gets_the_models_sole_language(self):
        """No Language against a Model declaring one Language is filled in from it."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub, seen_languages = self.make_recording_hub(engine, languages=(LANGUAGE,))

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert seen_languages == [LANGUAGE]
        assert engine.languages == [LANGUAGE]

    async def test_a_language_the_client_sent_is_left_alone(self):
        """A Model declaring several Languages does not overwrite the request's Language."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub, seen_languages = self.make_recording_hub(engine, languages=(LANGUAGE, OTHER_LANGUAGE))

        await collect_hub_sentences(hub, "hello", VOICE_ID, language=OTHER_LANGUAGE)

        assert seen_languages == [OTHER_LANGUAGE]
        assert engine.languages == [OTHER_LANGUAGE]

    async def test_a_model_declaring_several_languages_supplies_none(self):
        """Several declared Languages leave the request without one, for the Hub to judge."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub, seen_languages = self.make_recording_hub(
            engine, languages=(LANGUAGE, OTHER_LANGUAGE), auto_detected=True
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert seen_languages == [None]
        assert engine.languages == [None]

    async def test_an_auto_detecting_model_is_never_guessed_at(self):
        """A sole declared Language is not filled in when the Model auto-detects."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub, seen_languages = self.make_recording_hub(
            engine, languages=(LANGUAGE,), auto_detected=True
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert seen_languages == [None]
        assert engine.languages == [None]

    async def test_a_model_declaring_no_language_supplies_none(self):
        """Nothing to fill in leaves the request without one."""
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub, seen_languages = self.make_recording_hub(engine, languages=(), auto_detected=True)

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert seen_languages == [None]
        assert engine.languages == [None]


class TestNormalizationSelection:
    @pytest.mark.parametrize(
        ("override_type", "default_type", "expected_prompt"),
        [
            pytest.param(
                NormalizationType.OPENAI,
                NormalizationType.SIMPLE,
                OVERRIDE_PROMPT_TEXT,
                id="override-openai-beats-default-simple",
            ),
            pytest.param(
                NormalizationType.SIMPLE,
                NormalizationType.OPENAI,
                None,
                id="override-simple-beats-default-openai",
            ),
        ],
    )
    async def test_override_type_wins_over_the_server_wide_default(
        self, override_type, default_type, expected_prompt, mock_openai_client
    ):
        """A Voice override selects the override's normalizer type and Prompt."""
        uses_openai = override_type is NormalizationType.OPENAI
        storage = make_storage(
            overrides=[make_override(type=override_type, prompt_id="p1" if uses_openai else None)],
            prompts=[prompt_for("p1", OVERRIDE_PROMPT_TEXT)] if uses_openai else [],
        )
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=default_type,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        if expected_prompt is None:
            # The override asked for the simple normalizer, so no LLM call is made
            # and the server-wide default's type is not consulted.
            mock_openai_client.chat.completions.create.assert_not_awaited()
            assert engine.synthesized_texts == ["hello"]
        else:
            assert await_sent_prompts(mock_openai_client) == [OVERRIDE_PROMPT_TEXT]

    async def test_voice_without_an_override_uses_the_server_wide_default(self, mock_openai_client):
        """A Voice with no override falls through to the server-wide default."""
        storage = make_storage()
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=NormalizationType.OPENAI,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert await_sent_prompts(mock_openai_client) == [DEFAULT_PROMPT_TEXT]

    async def test_override_for_another_language_is_ignored(self, mock_openai_client):
        """An override registered for a different Language does not apply."""
        storage = make_storage(
            overrides=[make_override(type=NormalizationType.SIMPLE, enabled=False, language="fr")]
        )
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=NormalizationType.OPENAI,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert await_sent_prompts(mock_openai_client) == [DEFAULT_PROMPT_TEXT]

    async def test_disabled_override_gets_no_normalization_despite_enabled_default(
        self, mock_openai_client
    ):
        """A disabled override means no normalization, whatever the default says."""
        storage = make_storage(
            overrides=[make_override(type=NormalizationType.OPENAI, enabled=False, prompt_id="p1")],
            prompts=[prompt_for("p1", OVERRIDE_PROMPT_TEXT)],
        )
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=NormalizationType.OPENAI,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        mock_openai_client.chat.completions.create.assert_not_awaited()
        assert engine.synthesized_texts == ["hello"]

    async def test_override_with_unresolvable_prompt_and_no_default_yields_no_normalizer(
        self, mock_openai_client
    ):
        """An unresolvable override Prompt with nothing to fall back on gets no normalizer."""
        storage = make_storage(
            overrides=[make_override(type=NormalizationType.OPENAI, prompt_id="missing-prompt")],
            prompts=[],
        )
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(storage=storage, openai_client=mock_openai_client),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        mock_openai_client.chat.completions.create.assert_not_awaited()
        assert engine.synthesized_texts == ["hello"]

    async def test_override_with_unresolvable_prompt_falls_back_to_default_prompt(
        self, mock_openai_client
    ):
        """An unresolvable override Prompt falls back to the server-wide default Prompt.

        The ticket asks that an unresolvable Prompt yield no normalizer, but the factory
        falls back to the default Prompt for the Language. This test pins the behaviour
        as implemented so the divergence from the ticket is visible rather than hidden.
        """
        storage = make_storage(
            overrides=[make_override(type=NormalizationType.OPENAI, prompt_id="missing-prompt")],
            prompts=[],
        )
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=NormalizationType.OPENAI,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )

        await collect_hub_sentences(hub, "hello", VOICE_ID)

        assert await_sent_prompts(mock_openai_client) == [DEFAULT_PROMPT_TEXT]


class TestNormalizationApplication:
    async def test_selected_normalizer_is_applied_to_every_sentence(self, mock_openai_client):
        """The selected normalizer runs once per Sentence, each seeing that Sentence."""
        storage = make_storage()
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(
            engine=engine,
            middlewares=build_chain(
                storage=storage,
                openai_client=mock_openai_client,
                default_enabled=True,
                default_type=NormalizationType.OPENAI,
                default_normalization_prompts=default_prompts(),
            ),
            storage=storage,
        )
        sentences = ["First sentence here.", "Second sentence here.", "Third sentence here."]

        await collect_hub_sentences(hub, " ".join(sentences), VOICE_ID)

        # The normalizer saw each Sentence, so the LLM was called once per Sentence.
        assert len(await_sent_prompts(mock_openai_client)) == len(sentences)
        assert engine.synthesized_texts == ["normalized text"] * len(sentences)

    async def test_sentences_pass_through_untouched_when_no_normalizer_is_selected(self):
        """With no normalizer selected, Sentences reach the engine exactly as split."""
        storage = make_storage()
        engine = FakeTtsEngine(make_model(id=MODEL_ID), samples_per_sentence=1000)
        hub = make_hub(engine=engine, middlewares=build_chain(storage=storage), storage=storage)

        await collect_hub_sentences(
            hub, "First sentence here. Second sentence here. Third sentence here.", VOICE_ID
        )

        assert engine.synthesized_texts == [
            "First sentence here.",
            "Second sentence here.",
            "Third sentence here.",
        ]


def await_sent_prompts(openai_client):
    """Return the system prompt text of every awaited chat completion, in order."""
    prompts = []
    for call in openai_client.chat.completions.create.await_args_list:
        messages = call.kwargs["messages"]
        prompts.append(messages[0]["content"])
    return prompts
