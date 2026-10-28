---
title: "Qwen3-TTS voice cloning end to end"
labels:
  - completed
created: 2026-10-19
---

## What to build

An operator declares a Base Qwen3-TTS Model Info and Voices carrying **Reference
Audio**, and Wyoming synthesis returns speech in that cloned voice.

The TTS Engine downloads the checkpoint from the Model Info's upstream id into
the Models directory, at the pinned revision when one is declared. Before
loading, it reads the checkpoint's own declared type and accepts only Base
checkpoints; a VoiceDesign checkpoint is rejected with an error naming the
families that are supported, so the operator does not pay for a load before
finding out.

Synthesis maps the request **Language** to the checkpoint's language names. The
checkpoint accepts a small fixed set of English language names and an automatic
mode; this project's Language is a code. An unrecognised code falls back to
automatic detection with a warning rather than failing the request.

A Voice with Reference Audio is cloned through the Voice Prompt cache. A Voice
without Reference Audio on a Base Model Info is a configuration error naming the
Voice. A Voice with Reference Audio but no reference text is cloned from the
speaker embedding alone, with a warning that quality is reduced.

Output is mono 16-bit PCM at the checkpoint's own sample rate, so no resampling
is introduced.

Register the engine for the Qwen family on the torch backend, and narrow the
Engine Factory's declared-but-unimplemented test so only the OpenAI-compatible
family remains rejected.

## Acceptance criteria

- [x] A Base Model Info downloads into the Models directory, at the declared revision when one is set, and loads on the resolved device
- [x] A VoiceDesign checkpoint is rejected at warmup with an error naming the supported families
- [x] A Voice with Reference Audio synthesizes through the Voice Prompt cache
- [x] A Voice without Reference Audio on a Base Model Info raises an error naming the Voice
- [x] A Voice with Reference Audio but no reference text clones from the speaker embedding only and warns
- [x] Request Language codes map to the checkpoint's language names; unknown codes fall back to automatic detection and warn
- [x] Output is mono 16-bit PCM at the checkpoint's sample rate
- [x] The Engine Factory resolves a Qwen Model Info on the torch backend to this engine
- [x] The Engine Factory test rejects only the OpenAI-compatible family
- [x] Tests cover warmup, download and revision, checkpoint family detection, language mapping, both reference-audio paths, and audio conversion

## Blocked by

- [01: Make the Qwen3-TTS runtime available](01-make-the-qwen3-tts-runtime-available.md)
- [02: Pin a Model Info to an upstream model revision](02-pin-a-model-info-to-an-upstream-revision.md)
- [03: Voice Prompt cache shared by cloning engines](03-voice-prompt-cache-for-cloning-engines.md)
