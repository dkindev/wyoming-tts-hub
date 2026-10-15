---
title: "Frames carry the Chunk's announced width and channels (already satisfied)"
labels:
  - completed
created: 2026-10-15
---

## What to build

Nothing. This ticket is closed because the work it asked for is already done.

It was written from a review of the no-copy streaming commits, which found that the TTS
Engine Hub's framing path hardcoded 16-bit mono and ignored the width and channels each
Chunk declared. That finding was correct when made: the framing path passed module-level
constants instead of the Chunk's own values, so a Chunk of any other format would have
been announced to the Wyoming client as 16-bit mono.

It has since been fixed: the constants were removed, and every Frame now carries the width
and channels of the Chunk it was split from. Frames are also sliced in samples, so the
sample width does not affect where a Frame boundary falls.

The only 16-bit mono values left are the Silero TTS Engine declaring the format it
produces, which is the Engine's to declare.

## Acceptance criteria

- [x] Every Frame carries the width and channels of the Chunk it was split from
- [x] No 16-bit mono hardcode remains in the framing path
- [x] The only remaining 16-bit mono declaration is a TTS Engine declaring the format it
      produces
- [x] A test covers a Chunk whose width and channels are not 16-bit mono, at the Hub and at
      the Wyoming handler, so the property cannot silently lapse

## Notes

The first three criteria were satisfied before this ticket was closed, and closing it that
way was wrong in one respect: nothing tested them. The only framing test asserted 16-bit
mono, which is also what the fake TTS Engine produced, so it passed just as happily with
the framing path hardcoding 16-bit mono again. Reinstating the hardcode left every test
green.

The fake TTS Engine now declares the width and channels it produces, and audio is typed
to match, so a Chunk can be something other than 16-bit mono. Both new tests fail if the
format stops being carried, and both pass on the current code.

## Blocked by

- None (can start immediately)
