import inspect
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import replace
from typing import Generic, TypeVar

from src.tts.models import Voice

_T = TypeVar("_T")


class VoicePromptCache(Generic[_T]):
    """Reuse an expensive Voice Prompt across every sentence spoken in a Voice.

    A cloning TTS Engine builds a Voice Prompt from a Voice's Reference Audio, which
    is far too expensive to repeat for each Sentence. Callers hand this cache a Voice
    and a factory; the factory is asked to build the prompt only once for that Voice,
    its Reference Audio and its reference text.

    The cache knows nothing about the engine that builds the prompt. It is
    thread-safe so a TTS Engine can call it from the worker thread it uses for
    blocking work: concurrent callers asking for the same Voice wait for one build
    and share its result, while different Voices build independently.

    Capacity is bounded. The least recently used Voice Prompt is evicted when a new
    one would exceed it; calling `clear` drops every entry.
    """

    def __init__(self, capacity: int = 8):
        if capacity < 0:
            raise ValueError(f"Capacity cannot be negative, but got {capacity}")

        self._capacity = capacity
        self._entries: OrderedDict[Voice, _T] = OrderedDict()
        self._builds: dict[Voice, threading.Event] = {}
        self._generation = 0
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def capacity(self) -> int:
        """The most Voice Prompts this cache keeps at once."""
        return self._capacity

    def get_or_create(
        self,
        voice: Voice,
        factory: Callable[..., _T],
    ) -> _T:
        """Return the Voice Prompt for `voice`, building it with `factory` if needed.

        A factory may take the Voice as its only positional argument, or take none;
        the cache supplies the Voice when the factory requires it. A factory that
        raises leaves no entry behind, so the next caller tries again.
        """
        key = self._normalized(voice)

        while True:
            with self._lock:
                if key in self._entries:
                    return self._reuse(key)

                build = self._builds.get(key)
                if build is None:
                    build = threading.Event()
                    self._builds[key] = build
                    generation = self._generation
                    should_build = True
                else:
                    should_build = False

            if not should_build:
                build.wait()
                continue

            try:
                value = self._call_factory(factory, voice)
            except BaseException:
                self._finish_build(key, build)
                raise

            with self._lock:
                # A clear while the factory ran means this result belongs to the
                # generation that was cleared, so return it without resurrecting it.
                if self._generation == generation and self._capacity > 0:
                    self._entries[key] = value
                    self._entries.move_to_end(key)

                    while len(self._entries) > self._capacity:
                        self._entries.popitem(last=False)

            self._finish_build(key, build)
            return value

    def clear(self) -> None:
        """Drop every cached Voice Prompt, so the next caller builds again."""
        with self._lock:
            self._entries.clear()
            self._generation += 1

    def _finish_build(self, key: Voice, build: threading.Event) -> None:
        with self._lock:
            if self._builds.get(key) is build:
                del self._builds[key]

        build.set()

    def _reuse(self, key: Voice) -> _T:
        """Return an entry and mark it as the most recently used.

        The cache lock must already be held.
        """
        self._entries.move_to_end(key)
        return self._entries[key]

    @staticmethod
    def _normalized(voice: Voice) -> Voice:
        """Key a Voice with its Reference Audio resolved to an absolute path.

        The data file under a running server may be edited, so the Reference Audio
        and reference text are part of the key: changing either builds a new prompt
        rather than serving one from the old reference.
        """
        if not voice.ref_audio or os.path.isabs(voice.ref_audio):
            return voice

        return replace(voice, ref_audio=os.path.abspath(voice.ref_audio))

    @staticmethod
    def _call_factory(factory: Callable[..., _T], voice: Voice) -> _T:
        """Call a factory, passing the Voice when the factory asks for it."""
        try:
            parameters = tuple(inspect.signature(factory).parameters.values())
        except (TypeError, ValueError):
            parameters = ()

        for parameter in parameters:
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ) and (parameter.default is inspect.Parameter.empty or parameter.name == "voice"):
                return factory(voice)

            if parameter.kind is inspect.Parameter.KEYWORD_ONLY and parameter.name == "voice":
                return factory(voice=voice)

        return factory()
