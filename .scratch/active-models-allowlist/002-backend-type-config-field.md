---
title: "Add `backend_type` config field (dormant)"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Add a `backend_type: BackendType` setting to `Settings`, defaulting to `BackendType.TORCH`. It is declarative and consumed nowhere yet — it exists today only so a future `EngineFactory.create_engine(Model, BackendType)` can use it. Do not add runtime assertions against it, and do not touch `TTSEngine.get_backend_type()` or the `silero_engine` module (that method is dead code and stays as-is).

Wiring: the field is an enum, so existing plumbing already handles it — YAML (`backend_type: torch`), env var (`TTS_BACKEND_TYPE=torch`), and CLI (`--backend_type torch`) should just work via the existing enum branch in the CLI arg source.

## Acceptance criteria

- [x] `Settings` has `backend_type: BackendType` defaulting to `BackendType.TORCH`
- [x] `TTS_BACKEND_TYPE=torch` env var, `backend_type: torch` YAML, and `--backend_type torch` CLI flag all populate the setting
- [x] No runtime consumption added — no assertion against the setting, `get_backend_type()` / `silero_engine` untouched
- [x] Config tests cover the default and the env/YAML/CLI wiring

## Blocked by

None — can start immediately