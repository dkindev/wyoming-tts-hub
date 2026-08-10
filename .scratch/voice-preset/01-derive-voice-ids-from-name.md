---
title: "Derive voice IDs from the voice name (many voices per speaker)"
labels:
  - ready-for-agent
created: 2026-08-10
---

## Parent

This reverses the decision in `.scratch/normalization-language/02-model-speaker-voice-ids.md`, which derived voice IDs from the model-speaker pair. The parent issue is complete; its `<model_id>-<speaker>` framing is being replaced.

## What to build

A Voice is a user-facing preset anchored to a (Model, Speaker) pair, and a Model may declare multiple Voices that share one Speaker. Voice identity therefore comes from the voice name, not the speaker: `{model_id}-{voice_name}` instead of `{model_id}-{speaker}`.

`YamlDataStorage` builds the voice ID as `f"{model_id}-{voice_name}"`. The speaker remains the engine anchor the TTS engine selects during synthesis, and its existing defaulting is unchanged: when a voice omits or empties `speaker`, it defaults to the voice name. `name` stays a required field and is now also the uniqueness key within a model.

Two voices under one model with the same `speaker` but distinct names must both load and be individually addressable via their derived IDs (e.g. `aidar-soft` and `aidar-loud`, both `speaker: aidar`, become `v5_5_ru-aidar-soft` and `v5_5_ru-aidar-loud`).

Update the DataStorage tests:
- the locale-less schema test must expect the name-based ID for a voice with a distinct speaker (a `henry` voice with `speaker: en_2` under `v3_en` becomes `v3_en-henry`), and its lookup uses that ID,
- add a test that two voices sharing a `speaker` under one model both load with distinct name-based IDs and each resolves via `get_voice`.

## Acceptance criteria

- [x] Voice IDs are constructed as `{model_id}-{voice_name}` (speaker is no longer the identity key)
- [x] `speaker` still defaults to the voice name when absent or empty; `name` remains required
- [x] Two voices sharing a `speaker` under one model both load and are addressable by distinct `{model_id}-{voice_name}` IDs
- [x] Locale-less schema test updated: `v3_en-en_2` becomes `v3_en-henry`
- [x] New test: shared-speaker voices load with distinct IDs and resolve via `get_voice`

## Blocked by

None - can start immediately
