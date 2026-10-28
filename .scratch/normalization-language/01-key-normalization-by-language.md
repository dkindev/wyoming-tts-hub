---
title: "Key VoiceNormalization by language in config storage"
labels:
  - ready-for-agent
created: 2026-08-10
---

## What to build

A Voice's per-voice normalization override becomes language-keyed. Each voice's
`normalization` block in the data configuration file is a dict keyed by bare
language code (`ru`, `en`), and each language entry holds the per-text-format
overrides:

```yaml
models:
  v5_5_ru:
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: p1
            ssml:
              enabled: false
```

`VoiceNormalization` records now carry a `language` field (bare language code,
e.g. `ru`), and the storage keys them by `(voice_id, text_format, language)`
(the internal key is `"{voice_id}__{text_format}__{language}"`).

`YamlDataStorage` parses the language-keyed shape, preserving existing lenient
defaults: `enabled` defaults to `true`, `type` defaults to `simple`, and
non-`TextFormat` keys are skipped. `get_voice_normalization(voice_id,
text_format, language)` does an exact language match — a missing or mismatched
language returns `None` (the caller falls back to server-wide defaults). The
abstract `get_voice_normalization` signature on the `DataStorage` ABC gains the
`language` argument so it matches the implementation.

Update the DataStorage tests to the new schema: migrate the existing
VoiceNormalization test fixtures to the language-keyed YAML shape, pass the
language argument to every `get_voice_normalization` call, and assert the parsed
`language` round-trips onto the VoiceNormalization.

Update the **VoiceNormalization** term in `CONTEXT.md`: it becomes a
per-voice, per-text-format, per-language override, and the flagged ambiguities
section records that this reverses the earlier "do not read a `language:` key
from YAML" decision — VoiceNormalization language is YAML-stored as a bare code,
while Model language stays derived via the engine's model→language mapping.

## Acceptance criteria

- [x] A voice entry with `normalization: {ru: {text: ...}}` parses into a VoiceNormalization with `language == "ru"`
- [x] `get_voice_normalization(voice_id, TextFormat.TEXT, "ru")` returns the override; a different language returns `None`
- [x] Lenient defaults preserved: `enabled` defaults to true, `type` defaults to simple, invalid format keys skipped
- [x] Abstract `get_voice_normalization` signature includes `language` and matches the implementation
- [x] DataStorage VoiceNormalization tests migrated to the new schema and green; `vn.language` round-trip asserted
- [x] CONTEXT.md VoiceNormalization term documents the language keying and the reversal of the "no language from YAML" decision

## Blocked by

None - can start immediately
