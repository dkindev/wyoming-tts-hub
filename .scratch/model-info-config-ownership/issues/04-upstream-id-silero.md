---
title: "Use upstream_id for Silero artifacts"
labels:
  - ready-for-agent
created: 2026-10-27
---

## What to build

Make the Silero TTS Engine resolve its registry entry and local model filename by `upstream_id`, so a local Model Info id can differ from the Silero registry key. The local `id` remains the identity clients, `active_models`, and `warmup_models` use. Logs and operator-facing errors keep naming the local `id`.

A Model Info without an `upstream_id` behaves exactly as before because it falls back to `id`. Update the operator documentation where it describes how a Silero Model Info maps to its registry entry.

## Acceptance criteria

- [x] Silero resolves the `models.yml` registry entry by `upstream_id`
- [x] Silero stores and loads the local model file under `<upstream_id>.pt`
- [x] Silero logs and errors continue to name the local `id`
- [x] A Model Info without `upstream_id` behaves exactly as before
- [x] Tests cover a Silero Model Info whose `id` differs from `upstream_id`
- [x] README documents the Silero upstream identity

## Blocked by

- 03 — Add upstream_id and use it for Qwen3
