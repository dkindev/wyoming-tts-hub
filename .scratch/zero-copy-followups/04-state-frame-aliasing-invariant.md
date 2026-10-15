---
title: "State the frame-aliasing invariant for future TTS Engines"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

A TTS Engine author knows that a Chunk's audio may still be aliased by Frames streamed
after the Chunk was yielded, and therefore must not recycle or mutate the buffer it handed
over.

Since Frames became views, the audio the Wyoming handler writes can reference the exact
buffer a TTS Engine produced. The Silero TTS Engine is safe by accident — it allocates a
fresh tensor per yield — but nothing says so. The next engine that reuses a buffer, a pool,
or a scratch array would corrupt audio already in flight, and nothing in the code would
stop it.

## Acceptance criteria

- [ ] The glossary states that Frames are views over their Chunk's audio, and that a TTS
      Engine must not recycle or mutate the audio it has yielded
- [ ] The invariant is recorded where an engine author meets the Chunk and Frame terms
- [ ] The glossary's single-context layout is respected: no separate glossary file is created

## Blocked by

- None (can start immediately)