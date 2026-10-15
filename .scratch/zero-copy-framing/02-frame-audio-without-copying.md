---
title: "Frame audio without copying"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

A synthesised request streams byte-for-byte the same audio as it does today, but the Hub
no longer copies any of it on the way out.

Today the TTS Engine Hub splits each Chunk into frames and copies every frame into a fresh
buffer before handing it to the Wyoming handler, which writes those bytes to the socket.
Nothing in between needs its own copy: a frame can be a view over the Engine's audio, and
the Wyoming handler — the one component that knows the protocol wants bytes — can hand a
byte view of that frame straight to the socket.

The audio a client receives, the rate announced in `AudioStart`, and the frame boundaries
are all unchanged.

## Acceptance criteria

- [x] The TTS Engine Hub yields each frame as a view over the Chunk's audio rather than a
      copy of it
- [x] The Wyoming handler converts each frame to a byte view at the write, so the bytes on
      the wire are unchanged
- [x] A regression test asserts that all frames of one Sentence share memory with each
      other, and therefore fails if a per-frame copy is reintroduced
- [x] Total audio bytes across a Sentence's frames still equal what the TTS Engine produced
- [x] Frame-size and trailing-partial-frame assertions express their expectations in samples
- [x] Static analysis no longer reports the framing step handing bytes to an array-typed field
- [x] The full test suite passes

## Notes

Nothing hands `TtsResult` bytes now, so the tolerance for it is gone from
`TtsResult.__post_init__` and `audio` is honestly `np.ndarray` throughout.

## Blocked by

- 01-contiguous-engine-pcm.md