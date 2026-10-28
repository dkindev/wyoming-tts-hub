---
title: "Resolve Silero model language from the models registry instead of a static engine-side mapping"
labels:
  - ready-for-agent
created: 2026-08-14
---

## What to build

The **Silero TTS Engine** currently resolves which section of the Silero models
registry (the `models.yml` `tts_models` tree, keyed by language) owns a given
**Model** through a hard-coded, incomplete engine-side **Model**→**Language**
map. The map omits registry models that live under non-language sections such as
`indic`, `cyrillic`, and `multi`, and has already gone stale relative to the
registry.

Replace the static map with registry-driven resolution. Whenever the engine
needs the registry section that owns a **Model**, derive it from the registry
itself:

1. If the **Model** declares exactly one **Language**, check that section
   first. If the model id is present there, use it.
2. Otherwise (multi-language **Model**, or the declared single section does not
   contain the model id — common for non-language section keys like `indic`,
   `cyrillic`, `multi`), scan every `tts_models` section and use the first match.
3. If no section contains the model id, raise a clear `TTSEngineError` that
   names the model and tells the operator to delete the cached `models.yml` so
   it can be re-downloaded.

While in this resolution path, route the engine's stored config values
(`models_dir`, `models_yml_url`, `models_yml_hash`) into the lookup — the
current code reads a non-existent `config` object and would crash before
resolution even runs.

This delivers a working, unit-tested model-resolution path end-to-end: registry
loading, language derivation, section lookup, and local/downloaded model path
selection.

## Acceptance criteria

- [ ] The static model→language mapping is removed and no longer referenced
- [ ] A **Model** declaring a single **Language** that exists in that registry
      section resolves to it (fast path)
- [ ] A **Model** whose id lives under a non-language section (e.g. `cyrillic`)
      resolves by scanning even when its declared single **Language** does not
      match
- [ ] A multi-language **Model** resolves to the first matching section
- [ ] A **Model** present in no section raises a clear `TTSEngineError`
      encouraging a fresh `models.yml` download
- [ ] Unit tests cover all four resolution paths above
- [ ] `ruff` and `pytest tests/` are green

## Blocked by

None - can start immediately
