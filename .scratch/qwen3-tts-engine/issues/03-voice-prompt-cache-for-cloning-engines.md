---
title: "Voice Prompt cache shared by cloning engines"
labels:
  - completed
created: 2026-10-19
---

## What to build

A **Voice Prompt** is expensive to build — it encodes the Voice's **Reference
Audio** and extracts a speaker embedding — and the same one is reused for every
sentence spoken in that Voice. Build the cache that any cloning TTS Engine can
use to build a Voice Prompt once and reuse it.

It must be safe to call from the worker threads engines use for blocking work:
two concurrent requests for the same Voice must build exactly one Voice Prompt.
It is keyed by the Voice, its resolved Reference Audio, and its reference text,
so editing the data file under a running server cannot keep serving a prompt
built from the old reference.

The cache holds no knowledge of any particular engine: callers hand it a Voice
and a factory, and it hands back whatever the factory produced.

## Acceptance criteria

- [x] `get_or_create` returns the factory's result and calls the factory at most once per key
- [x] Concurrent callers for the same key produce exactly one factory call
- [x] Different Voices, different Reference Audio, or different reference text each produce a separate entry
- [x] Relative Reference Audio paths are resolved to absolute before keying; absolute paths are left unchanged
- [x] Capacity is bounded, with least-recently-used eviction and a clear operation
- [x] The module imports nothing engine- or provider-specific
- [x] Tests cover reuse, concurrency, key separation, path resolution, eviction, and clearing

## Blocked by

None — can start immediately
