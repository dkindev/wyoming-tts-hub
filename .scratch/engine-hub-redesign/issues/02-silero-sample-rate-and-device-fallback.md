---
title: "Sample-rate selection and device fallback for the Silero TTS Engine"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

A Silero Model publishes the sample rates it supports in the registry. When the
server is configured for a rate the Model does not support, the TTS Engine must
land on the nearest supported rate rather than failing or silently producing
mismatched audio. Separately, when the configured compute device is unavailable
on the host, the TTS Engine must fall back to CPU and still synthesize.

Both behaviours were covered before the Engine Hub redesign, against an engine
class that no longer exists. Re-express them against the current Silero TTS
Engine.

Sample-rate selection to cover:

- A Model supporting a single rate always uses that rate, whatever is configured.
- A configured rate above the Model's maximum clamps down to the maximum.
- A configured rate below the Model's minimum clamps up to the minimum.
- A configured rate the Model supports exactly is used as-is.
- A configured rate between two supported rates uses the highest supported rate
  below it.
- A Model publishing no sample rates uses the configured rate.

Device fallback to cover:

- Requesting `cuda` on a host without CUDA produces CPU audio.
- Requesting `xpu` on a host without XPU produces CPU audio.

Also cover the registry resolution that precedes both: a Model resolves to the
registry section that owns it, preferring its sole declared Language and falling
back to a scan across sections, and a Model owned by no section is rejected with
an error naming the Model and pointing at the cached registry file.

## Acceptance criteria

- [x] A Model declaring `[8000, 24000]` synthesizes at 24000 when the server is
      configured for 48000
- [x] A Model declaring `[24000, 48000]` synthesizes at 24000 when configured for
      8000, and at 24000 when configured for 44100
- [x] A Model declaring one rate uses that rate regardless of configuration
- [x] A Model declaring no sample rates synthesizes at the configured rate
- [x] Requesting `cuda` on a host without CUDA synthesizes at the CPU device
- [x] Requesting `xpu` on a host without XPU synthesizes at the CPU device
- [x] Registry errors are raised as runtime errors naming the Model and the
      registry file

## Blocked by

- [01: Restore a runnable test suite](01-restore-runnable-test-suite.md)