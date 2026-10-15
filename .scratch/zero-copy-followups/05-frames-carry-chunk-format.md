---
title: "Frames carry the Chunk's announced width and channels"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

A Chunk that is not 16-bit mono is framed and announced faithfully.

Every Frame announces its width and channels, but the TTS Engine Hub's framing path
hardcodes 16-bit mono and ignores the width and channels the Chunk itself declares. Any
future TTS Engine producing wider samples or more than one channel would be announced to
the Wyoming client with the wrong format, and the client would decode it as noise.

This is pre-existing, but the change that made audio a view made it more load-bearing: the
Chunk's own audio now carries its format, and the framing path reads the array's length
while ignoring the array's declared width.

## Acceptance criteria

- [ ] Each Frame announces the width and channels of the Chunk it was split from
- [ ] The hardcoded 16-bit-mono assumption is gone from the framing path
- [ ] Frame boundaries are derived from the Chunk's declared width, so a non-16-bit Chunk is
      split into correctly sized Frames
- [ ] A test covers a Chunk whose width or channels differ from 16-bit mono, and the existing
      framing tests still pass

## Blocked by

- None (can start immediately)