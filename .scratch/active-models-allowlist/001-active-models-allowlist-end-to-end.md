---
title: "Add `active_models` runtime allowlist (end-to-end)"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Add an `active_models: list[str]` setting: a strict runtime allowlist of model ids that a running instance actually serves. A **Model** is served iff it is `enabled` in the model config **and** its id is listed in `active_models`. Only served models' **Voices** are advertised and synthesized; voices referencing dropped models are dropped too. The allowlist is layered on top of the existing `enabled` filtering, not an override: a model listed in `active_models` but disabled in the config stays unserved (log a warning, do not fail).

The setting is mandatory at boot: an empty or missing `active_models` is a validation error, and the server refuses to start. Unknown ids (not declared anywhere in the model config) also fail boot, naming the offending ids. The id availability cross-check happens in the storage factory (`create_storage`), against the full set of declared model ids (pre-filter).

Wiring for the setting: YAML list (`active_models: [a, b]`), env var as JSON (`TTS_ACTIVE_MODELS=["a","b"]`), and CLI as a repeated flag (`--active_models a --active_models b`). The CLI arg source needs a new branch for array-typed settings — repeated `action="append"` rather than the current string fallback.

Implemented decisions (from grilling session): whole slice must land as one unit — the mandatory non-empty validation cannot ship before its consumer exists, or every existing deployment fails to boot.

## Acceptance criteria

- [x] `Settings` has `active_models: list[str]`; empty or missing resolves to a startup validation error
- [x] `TTS_ACTIVE_MODELS=["a","b"]` (JSON), `active_models: [a, b]` (YAML), and repeated `--active_models` CLI flags all populate the setting; CLI source handles array-typed fields
- [x] A **Model** is served iff `enabled` AND listed in `active_models`; voices of non-served models are not advertised
- [x] An `active_models` id that exists but is `enabled: false` stays unserved with a warning logged
- [x] A config that declares model ids and an unknown id in `active_models` fails at startup via the storage factory, naming the unknown id(s)
- [x] Tests cover: settings validation, all three wiring paths, intersection semantics, voice dropping, unknown-id boot failure, listed-but-disabled warning

## Blocked by

None — can start immediately