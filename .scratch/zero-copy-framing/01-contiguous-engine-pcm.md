---
title: "Guarantee contiguous PCM from a TTS Engine"
labels:
  - completed
created: 2026-10-15
---

## What to build

Every `TtsResult` a TTS Engine yields holds audio that is C-contiguous, so that audio can
be addressed as raw bytes anywhere downstream of the Engine without a defensive copy.

A strided audio array cannot be cast to a byte view, so a non-contiguous Chunk would only
surface much later, as a cast failure at the Wyoming boundary. The guarantee therefore
belongs on the shared audio type rather than in each TTS Engine: a Chunk cannot leave a
TTS Engine strided even if the Engine forgets to ask for contiguous audio, and no Engine
has to remember to. It costs one flag check where audio is constructed, and nothing at
all when the audio is already contiguous.

Nothing visible to a client changes: the audio, its sample rate, bytes per sample and
channel count are all identical.

## Acceptance criteria

- [x] Audio handed over as a `TtsResult` is C-contiguous from the moment it is
      constructed, so no TTS Engine can yield a strided Chunk even if it never asks for
      contiguous audio itself
- [x] No copy is introduced when the audio is already contiguous
- [x] A test asserts that audio yielded by a TTS Engine is C-contiguous
- [x] No existing test lost coverage: the shared fake TTS Engine gained the ability to emit
      strided audio, and every pre-existing assertion still runs

## Notes

The guarantee is made in `TtsResult.__post_init__` rather than in the Silero TTS Engine:
a Chunk cannot leave a TTS Engine strided even if the Engine forgets, and no Engine has to
remember. Silero gets it through the type.

## Blocked by

- None (can start immediately)