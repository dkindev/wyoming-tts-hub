---
title: "Reject duplicate voice IDs at startup"
labels:
  - ready-for-agent
created: 2026-08-10
---

## Parent

This is a follow-up to `.scratch/voice-preset/01-derive-voice-ids-from-name.md`. With the voice ID derived from `{model_id}-{voice_name}`, two voice entries in the same model with the same `name` would derive the same ID.

## What to build

`YamlDataStorage` must fail loudly instead of silently overwriting when two voice entries under the same model derive the same voice ID (i.e. duplicate `name` within a model). Loading such a config raises a clear error (e.g. `ValueError`) that names the offending duplicate IDs.

This turns the current silent last-wins dict collision into an authoring error surfaced at startup. Valid configs are unaffected, including configs where several voices share one `speaker` but have distinct names (that case must continue to load).

Add coverage:
- a config with duplicate voice names in one model raises the error,
- a config with distinct names sharing a speaker loads without error.

## Acceptance criteria

- [x] Duplicate derived voice ID raises a clear error naming the duplicate IDs
- [x] A config with several distinct-named voices sharing one speaker still loads without error
- [x] Test added for the duplicate-name collision

## Blocked by

- `.scratch/voice-preset/01-derive-voice-ids-from-name.md`
