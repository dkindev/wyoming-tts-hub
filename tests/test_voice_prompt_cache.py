import os
import threading
import time

import pytest

from src.tts.models import Voice
from src.tts.voice_prompt_cache import VoicePromptCache


def make_voice(**overrides) -> Voice:
    fields = {
        "id": "qwen-voice",
        "name": "Voice",
        "speaker": "voice",
        "model_id": "qwen",
        "ref_audio": "reference.wav",
        "ref_text": "Reference text",
    }
    fields.update(overrides)
    return Voice(**fields)


class TestReuse:
    def test_returns_the_factory_result(self):
        cache = VoicePromptCache(capacity=4)

        assert cache.get_or_create(make_voice(), lambda: "prompt") == "prompt"

    def test_calls_the_factory_once_for_the_same_voice(self):
        cache = VoicePromptCache(capacity=4)
        voice = make_voice()
        calls = []

        def factory():
            calls.append(voice.id)
            return "prompt"

        first = cache.get_or_create(voice, factory)
        second = cache.get_or_create(voice, factory)

        assert first == second == "prompt"
        assert calls == [voice.id]

    def test_calls_a_factory_that_takes_the_voice(self):
        cache = VoicePromptCache(capacity=4)
        voice = make_voice()
        calls = []

        def factory(for_voice):
            calls.append(for_voice)
            return for_voice.id

        assert cache.get_or_create(voice, factory) == voice.id
        assert calls == [voice]


class TestConcurrency:
    def test_concurrent_callers_for_one_voice_build_once(self):
        cache = VoicePromptCache(capacity=4)
        voice = make_voice()
        calls = []
        build_started = threading.Event()
        release_build = threading.Event()
        results = []
        errors = []

        def factory():
            calls.append(voice)
            build_started.set()
            assert release_build.wait(timeout=5)
            return "prompt"

        def call():
            try:
                results.append(cache.get_or_create(voice, factory))
            except BaseException as error:
                errors.append(error)

        first = threading.Thread(target=call)
        second = threading.Thread(target=call)

        first.start()
        assert build_started.wait(timeout=5)
        second.start()
        time.sleep(0.05)
        release_build.set()

        first.join(timeout=5)
        second.join(timeout=5)

        assert errors == []
        assert calls == [voice]
        assert results == ["prompt", "prompt"]

    def test_clear_during_a_build_does_not_restore_the_result(self):
        cache = VoicePromptCache(capacity=4)
        voice = make_voice()
        started = threading.Event()
        release = threading.Event()
        results = []

        def factory():
            started.set()
            assert release.wait(timeout=5)
            return "prompt"

        def call():
            results.append(cache.get_or_create(voice, factory))

        builder = threading.Thread(target=call)
        builder.start()
        assert started.wait(timeout=5)
        cache.clear()
        release.set()
        builder.join(timeout=5)

        assert results == ["prompt"]
        assert len(cache) == 0
        assert cache.get_or_create(voice, lambda: "rebuilt") == "rebuilt"

    def test_a_failed_build_is_not_cached(self):
        cache = VoicePromptCache(capacity=4)
        voice = make_voice()

        def fail():
            raise RuntimeError("cannot build")

        with pytest.raises(RuntimeError, match="cannot build"):
            cache.get_or_create(voice, fail)

        assert len(cache) == 0
        assert cache.get_or_create(voice, lambda: "prompt") == "prompt"


class TestKeySeparation:
    def test_different_voices_are_separate_entries(self):
        cache = VoicePromptCache(capacity=4)
        calls = []

        def factory():
            calls.append(1)
            return object()

        cache.get_or_create(make_voice(id="voice-a"), factory)
        cache.get_or_create(make_voice(id="voice-b"), factory)

        assert len(calls) == 2
        assert len(cache) == 2

    def test_different_reference_audio_is_separate_entries(self):
        cache = VoicePromptCache(capacity=4)
        calls = []

        def factory():
            calls.append(1)
            return object()

        cache.get_or_create(make_voice(ref_audio="first.wav"), factory)
        cache.get_or_create(make_voice(ref_audio="second.wav"), factory)

        assert len(calls) == 2
        assert len(cache) == 2

    def test_different_reference_text_is_separate_entries(self):
        cache = VoicePromptCache(capacity=4)
        calls = []

        def factory():
            calls.append(1)
            return object()

        cache.get_or_create(make_voice(ref_text="first text"), factory)
        cache.get_or_create(make_voice(ref_text="second text"), factory)

        assert len(calls) == 2
        assert len(cache) == 2


class TestReferenceAudioPaths:
    def test_relative_and_absolute_paths_to_the_same_audio_share_an_entry(self):
        cache = VoicePromptCache(capacity=4)
        absolute_path = os.path.abspath("reference.wav")
        voices = [
            make_voice(ref_audio="reference.wav"),
            make_voice(ref_audio=absolute_path),
            make_voice(ref_audio="./reference.wav"),
        ]
        calls = []

        def factory():
            calls.append(1)
            return "prompt"

        for voice in voices:
            assert cache.get_or_create(voice, factory) == "prompt"

        assert calls == [1]
        assert len(cache) == 1

    def test_an_absolute_path_is_not_rebased_when_the_working_directory_changes(self):
        cache = VoicePromptCache(capacity=4)
        absolute_path = os.path.abspath("/audio/reference.wav")
        calls = []

        def factory():
            calls.append(1)
            return "prompt"

        cache.get_or_create(make_voice(ref_audio=absolute_path), factory)

        old_cwd = os.getcwd()
        try:
            os.chdir("/tmp")
            cache.get_or_create(make_voice(ref_audio=absolute_path), factory)
        finally:
            os.chdir(old_cwd)

        assert calls == [1]


class TestCapacity:
    def test_least_recently_used_entry_is_evicted(self):
        cache = VoicePromptCache(capacity=2)
        first = make_voice(id="first")
        second = make_voice(id="second")
        third = make_voice(id="third")
        calls = []

        def factory():
            calls.append(1)
            return object()

        cache.get_or_create(first, factory)
        cache.get_or_create(second, factory)
        cache.get_or_create(first, factory)
        cache.get_or_create(third, factory)

        assert len(cache) == 2
        assert len(calls) == 3

        cache.get_or_create(first, factory)
        assert len(calls) == 3

        cache.get_or_create(second, factory)
        assert len(calls) == 4

    def test_capacity_of_zero_stores_nothing(self):
        cache = VoicePromptCache(capacity=0)

        assert cache.get_or_create(make_voice(), lambda: "prompt") == "prompt"
        assert len(cache) == 0

    def test_clearing_removes_every_entry(self):
        cache = VoicePromptCache(capacity=4)
        calls = []

        def factory():
            calls.append(1)
            return "prompt"

        cache.get_or_create(make_voice(id="first"), factory)
        cache.get_or_create(make_voice(id="second"), factory)

        cache.clear()

        assert len(cache) == 0
        cache.get_or_create(make_voice(id="first"), factory)
        assert len(calls) == 3
