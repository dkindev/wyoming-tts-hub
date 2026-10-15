---
title: "Guarantee contiguous PCM from a TTS Engine"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

Every `TtsResult` a TTS Engine yields holds audio that is C-contiguous, so that audio can
be addressed as raw bytes anywhere downstream of the Engine without a defensive copy.

The Silero TTS Engine converts its synthesised tensor into an array and hands it over
directly. A strided array cannot be cast to a byte view, so a non-contiguous result would
only surface much later, as a cast failure at the Wyoming boundary. The guarantee belongs
at the point the Engine hands audio over, where it is cheap and where it is one word wide.

Nothing visible to a client changes: the audio, its sample rate, bytes per sample and
channel count are all identical.

## Acceptance criteria

- [x] The Silero TTS Engine marks its audio contiguous before yielding it as a `TtsResult`
- [x] No copy is introduced when the audio is already contiguous
- [x] A test asserts that audio yielded by a TTS Engine is C-contiguous
- [x] Existing tests pass unchanged

## Notes

The guarantee is made in `TtsResult.__post_init__` rather than in the Silero TTS Engine:
a Chunk cannot leave a TTS Engine strided even if the Engine forgets, and no Engine has to
remember. Silero gets it through the type.

## Blocked by

- None (can start immediately)