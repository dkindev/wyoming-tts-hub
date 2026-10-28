---
title: "TTS Engine Manager owns Model loading, eviction, and shutdown"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

The TTS Engine Manager is the largest untested surface left by the redesign —
it owns the whole lifecycle of a loaded Model: when it is loaded, how long it is
kept, what happens when several requests share it, and how it is released at
shutdown.

Deliver the following observable behaviour, using a fake TTS Engine so no real
model is loaded:

**Warmup.** At startup the manager loads only the Models flagged to warm up. A
Model that fails to warm up is skipped with an error logged, and the others still
load. Warmup is a no-op when Models are already loaded.

**On-demand loading.** A Model is loaded the first time a request needs it, and
the same loaded engine is reused by every later request for that Model rather
than being rebuilt.

**Concurrency.** Each Model's sentences are bounded by the configured per-Model
concurrency limit. With the limit set to two, a third concurrent sentence for the
same Model waits rather than proceeding.

**Eviction.** When the cache is over capacity, the least-recently-used Model is
evicted and its engine closed. A Model that is still in use by an in-flight
request is *not* closed immediately — eviction is deferred until the last
request releases it, and only then is it closed.

**Shutdown.** Shutting the manager down closes every engine it still holds
exactly once, including those deferred from eviction. Shutting down twice is
harmless. Using the manager after shutdown is an error.

## Acceptance criteria

- [x] Warmup loads only Models flagged for warmup
- [x] A Model that raises during warmup is skipped and the remaining Models still
      load
- [x] Warmup does nothing when Models are already loaded
- [x] The first request for a Model loads its engine; a second request reuses the
      same engine instance
- [x] With the per-Model concurrency limit set to two, no more than two sentences
      for one Model synthesize at once
- [x] An evicted Model's engine is closed exactly once
- [x] A Model held by an in-flight request is closed only after that request
      completes
- [x] Shutdown closes every remaining engine exactly once, and is safe to call
      twice
- [x] Requesting a Model after shutdown raises an error
- [x] No test reaches into the manager's private caches or task handles

## Blocked by

- [03: Engine Hub routes a Voice to its Model and frames the audio](03-engine-hub-routing-and-framing.md)