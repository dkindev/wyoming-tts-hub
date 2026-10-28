---
title: "Update domain context: Voice is a preset (many voices per speaker)"
labels:
  - ready-for-human
created: 2026-08-10
---

## Parent

Docs companion to `.scratch/voice-preset/01-derive-voice-ids-from-name.md`. Records the reversal of the `<model_id>-<speaker>` voice identity framing established in `.scratch/normalization-language/02-model-speaker-voice-ids.md`.

## What to build

Update `CONTEXT.md` to frame a Voice as a user-facing preset anchored to a (Model, Speaker) pair, with many Voices able to map to one Speaker. Keep the glossary domain-level — do not couple it to implementation details.

- **Voice** term: a preset anchored to a (Model, Speaker) pair. It bundles a display **name** (which also identifies it within the Model) and optional synthesis properties — reference audio and text (`ref_audio`, `ref_text`), an instruct-style synthesis instruction (`instruct`) — plus per-text-format, per-language normalization overrides. Multiple Voices can map to the same Speaker within a Model, each differing in these properties. The Voice's identifier form is `<model_id>-<voice_name>`.
- **Speaker** term: sharpen as the engine-level Silero voice profile within a Model that the TTS engine selects during synthesis. One or more Voices can map to the same Speaker.
- **Relationships**: add "a Speaker within a Model may be referenced by one or more Voices"; keep the existing Model↔Speaker ownership lines.
- **Flagged ambiguities**: record that this reverses the earlier "voice ID derived from the model-speaker pair" decision — voice identity is derived from the model and the voice name, which is what lets multiple Voices share a Speaker.
- Reconcile the example dialogue and any Voice references so they stay consistent with the preset framing and the `<model_id>-<voice_name>` ID form.

## Acceptance criteria

- [x] Voice term defines the preset framing, the property list, and the `<model_id>-<voice_name>` ID
- [x] Speaker term sharpened as the engine-level profile; "one or more Voices per Speaker" relationship added
- [x] Flagged ambiguities records the reversal of the `<model_id>-<speaker>` decision
- [x] Example dialogue and remaining Voice references consistent with the new framing

## Blocked by

- `.scratch/voice-preset/01-derive-voice-ids-from-name.md`
