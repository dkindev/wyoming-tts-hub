---
title: "Record what actually shipped in the zero-copy tickets"
labels:
  - completed
created: 2026-10-15
---

## What to build

The landed zero-copy tickets describe the behaviour that actually shipped, so the next
agent who reads them is not misled by acceptance criteria marked done that the code does
not satisfy.

Two criteria drifted during implementation. The contiguity guarantee was specified as the
Silero TTS Engine's job and shipped as a guarantee on the shared audio type instead — a
better home, but not what the criterion says. The shared-memory regression test was
specified as Frames sharing memory with each other, which is unsatisfiable because Frames
cover disjoint ranges; what the test asserts, and why, is Frames sharing memory with the
Chunk they came from.

## Acceptance criteria

- [x] The contiguity criterion names where the guarantee actually lives, not the TTS Engine
      that was originally specified to hold it
- [x] The shared-memory criterion describes what the regression test asserts and why Frames
      cannot share memory with each other
- [x] No criterion remains marked satisfied that the committed code does not meet
- [x] The deviation notes explaining each change are kept

## Blocked by

- None (can start immediately)