---
title: "Align operator examples with the shipped Model Info ids"
labels:
  - ready-for-agent
created: 2026-10-28
---

## What to build

Update the operator-facing examples to use the local Model Info ids the shipped
data file now declares, and show how each local id maps to its upstream artifact.

The README's discovery example, Silero model example, Qwen3-TTS example, voice-id
example, and voice-normalization example should name `silero_ru`, `silero_en`,
`qwen3_base`, and `qwen3_custom_voice` rather than the old upstream names. The
Silero and Qwen3-TTS examples should declare each model's `upstream_id`, and the
cache-path examples should make the local-to-upstream mapping explicit. The
benchmark usage example should name `silero_ru-aidar`.

The README contract tests should look up the local ids, assert the documented and
shipped Qwen3-TTS entries carry their expected `upstream_id`, and use the new
Silero ids in the normalization example.

Leave `qwen3_voice_design` and its documentation untouched.

## Acceptance criteria

- [x] README examples and prose use the shipped local Model Info ids
- [x] README Silero and Qwen3-TTS examples show each model's `upstream_id`
- [x] README cache-path examples make the local-to-upstream mapping explicit
- [x] The benchmark usage example names the new Silero voice id
- [x] README contract tests look up local ids and assert the expected upstream ids
- [x] README contract tests use the new Silero id in the normalization example
- [x] `qwen3_voice_design` is not added to or changed in the documentation or tests

## Blocked by

None (can start immediately).
