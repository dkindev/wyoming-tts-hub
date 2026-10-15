---
title: "Resolve the byte-view type mismatch at the Wyoming boundary"
labels:
  - completed
created: 2026-10-15
---

## What to build

The audio the Wyoming handler writes is statically checked, and the comment beside it
describes what is actually passed.

Turning a Frame into a byte view moved the frame/bytes type mismatch rather than removing
it: static analysis now reports that a memoryview is being handed to a constructor that
declares it wants bytes. The wire itself is fine — Wyoming writes whatever buffer it is
given — but the claim in the source and the check disagree, and the disagreement should be
resolved honestly rather than left as a known error.

The audio must still reach the socket as a view. Converting it to bytes to satisfy the
annotation would undo the point of the change.

## Acceptance criteria

- [x] Static analysis reports no type error where the Wyoming handler builds its audio chunk
- [x] The audio still reaches the socket as a view, never copied into a fresh buffer
- [x] The comment at that site states what is passed, and matches the annotation of the
      Wyoming constructor rather than claiming a conversion that does not happen
- [x] No other static-analysis finding changes; the pre-existing findings elsewhere in the
      TTS Engine Hub are left alone

## Blocked by

- None (can start immediately)