---
title: "Qwen3-TTS preset speakers end to end"
labels:
  - completed
created: 2026-10-19
---

## What to build

An operator declares a CustomVoice Qwen3-TTS Model Info and Voices that name a
preset **Speaker**, optionally with an instruction. Synthesis returns speech in
that Speaker's timbre, with the instruction applied. No Reference Audio and no
Voice Prompt are involved.

The engine dispatches on the checkpoint type it already reads at warmup, so a
CustomVoice checkpoint and a Base checkpoint are served by the same TTS Engine.
An unsupported Speaker or Language is surfaced as a clear error rather than a
silent fallback.

One CustomVoice size ignores instructions entirely. Warn when an instruction is
configured on a checkpoint that will not apply it, so the operator is not left
believing it took effect.

## Acceptance criteria

- [x] A CustomVoice Model Info loads and synthesizes using the Voice's Speaker
- [x] A Voice's instruction is passed through and applied
- [x] An unsupported Speaker or Language produces a clear error naming the rejected value
- [x] An instruction configured on a checkpoint that ignores instructions produces a warning
- [x] No Voice Prompt is built for CustomVoice synthesis
- [x] Tests cover family dispatch, speaker and instruction pass-through, rejected values, and the ignored-instruction warning

## Blocked by

- [04: Qwen3-TTS voice cloning end to end](04-qwen3-tts-voice-cloning-end-to-end.md)
