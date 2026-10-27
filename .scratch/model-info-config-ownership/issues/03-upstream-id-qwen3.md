---
title: "Add upstream_id and use it for Qwen3"
labels:
  - ready-for-agent
created: 2026-10-27
---

## What to build

Let a Model Info name a different upstream artifact than its local id. Add an optional `upstream_id` to the Model Info, read from the data file. A non-empty string is used as written after trimming; an absent, null, empty, or whitespace-only value falls back to the Model Info's `id`; any other type fails with an error naming the Model Info.

The Qwen3-TTS engine fetches its checkpoint repository and caches it under the Models directory using `upstream_id`, while the local `id` remains the identity clients, `active_models`, and `warmup_models` use. Logs and operator-facing errors keep naming the local `id`. Model Infos without an `upstream_id` behave exactly as before because it falls back to `id`.

Add the **Upstream Id** term to the glossary and document the field in the operator documentation.

## Acceptance criteria

- [x] A Model Info carries an optional `upstream_id`
- [x] The data-file parser trims a string value and falls back to `id` for absent, null, empty, or whitespace-only values
- [x] A non-string `upstream_id` fails with an error naming the Model Info
- [x] Qwen3 uses `upstream_id` for the upstream repository id and the checkpoint cache path
- [x] Qwen3 logs and errors continue to name the local `id`
- [x] A Model Info without `upstream_id` behaves exactly as before
- [x] Tests cover the fallback cases, the explicit value, the invalid type, and Qwen3 artifact resolution
- [x] GLOSSARY and README document the upstream identity

## Blocked by

- 02 — Add warmup_models and derive Model Info warmup in storage
