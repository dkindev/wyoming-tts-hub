---
title: "Document Qwen3-TTS configuration for operators"
labels:
  - completed
created: 2026-10-19
---

## What to build

The operator-facing documentation still says Silero is the only implemented TTS
Engine, which stops being true the moment the Qwen engine registers. Bring it up
to date and ship a working example so someone can enable the engine without
reading the source.

Explain the two supported checkpoint families and what each needs from a Voice:
Base checkpoints clone from Reference Audio, CustomVoice checkpoints use a
preset Speaker with an optional instruction. Explain how to pin a revision, where
checkpoints are cached, and the automatic-detection caveat for the two dialect
speakers.

The shipped example must be inert: declaring a model without activating it must
not make a fresh boot download several gigabytes.

## Acceptance criteria

- [x] The README no longer claims Silero is the only implemented engine, and names both supported Qwen checkpoint families
- [x] A copy-pasteable example shows a Base Model Info with a cloning Voice and a CustomVoice Model Info with a preset Speaker
- [x] The example shows an optional revision pin
- [x] The shipped example is declared but not activated, so a fresh boot downloads nothing
- [x] The README states where checkpoints are cached and documents the automatic-detection and dialect caveat
- [x] Documentation examples are covered by the existing README example tests

## Blocked by

- [04: Qwen3-TTS voice cloning end to end](04-qwen3-tts-voice-cloning-end-to-end.md)
- [05: Qwen3-TTS preset speakers end to end](05-qwen3-tts-preset-speakers-end-to-end.md)
