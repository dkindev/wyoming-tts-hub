---
title: "Align the benchmark script with current vocabulary and types"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

The benchmark script at the repo root still uses the retired pre-rename
vocabulary: "chunk" for what is now a **Sentence**, and a cache class that no
longer exists. It therefore does not run against the current server.

Bring it back to the current vocabulary — **Sentence**, **Chunk**, **Frame** —
and to the types that actually exist today.

## Acceptance criteria

- [x] The benchmark imports no type that has been removed
- [x] It uses **Sentence**, **Chunk** and **Frame** as the glossary defines them
- [x] It runs end to end against the current server

## Answer

The script was rebuilt rather than repaired: what was at the root was an orphan
fragment with no imports, no entry point, and a `CachedModel` type that no longer
exists. It now wires the stack the way `src/main` does and serves it on a free
loopback port, driven by a real Wyoming client.

Each of the three counts is read where that unit actually exists, which is what
makes them worth reporting separately:

- **Sentence** — a middleware last in the chain, counting what splitting and
  normalization handed on to synthesis
- **Chunk** — the engine wrapper, counting what the TTS Engine yields for a Sentence
  before the Hub has sliced it
- **Frame** — the client, counting the audio events that reached the wire

Two findings from running it, both worth knowing:

- A **Model Info** declares the Languages it can speak, and Silero's Russian model
  raises on Latin script, so the sample text is chosen from the Voice's declared
  Language rather than fixed. Asking for the wrong one measures an error, not a speed.
- Peak memory on cpu has no resettable counter, so the report says
  "process peak RSS, lifetime" rather than passing a lifetime figure off as what one
  request cost. The device figure is reset after warmup, when a device is known.

## Blocked by

None - can start immediately