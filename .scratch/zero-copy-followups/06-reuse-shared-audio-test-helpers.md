---
title: "Reuse the shared audio-capture helpers in the streaming tests"
labels:
  - completed
created: 2026-10-15
---

## What to build

The streaming tests read audio out of the Wyoming wire through the shared helpers, instead
of each one assembling its own.

The zero-copy work left three kinds of duplication behind: a handler test joins chunk
payloads by hand although the same file already has a helper for it and the shared test
helpers gained one; three separate tests restate the same strided-audio contract; and a
new test uses a single-element loop to unwrap one event. Each copy is a place for the
streaming tests to drift apart.

## Acceptance criteria

- [x] The handler test that reads audio off the wire uses the shared helper instead of
      inlining its own join
- [x] The strided-audio arrangement is expressed once, not restated per test
- [x] The single-element loop used to unwrap one event is gone
- [x] No test loses coverage: the same assertions still run

## Blocked by

- None (can start immediately)
