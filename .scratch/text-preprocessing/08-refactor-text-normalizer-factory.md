---
id: 8
title: "Refactor TextNormalizerFactory to language-keyed create()"
labels:
  - ready-for-agent
created: 2026-08-14
---

## What to build

Refactor `TextNormalizerFactory` so a caller holding a **Voice**, a **Text
Format**, and a bare **Language** code can obtain a `TextNormalizer` — the
shape the upcoming `TtsEngineHub.synthesize_pcm(..., language)` will provide —
without any dependency on a voice locale.

The current factory's public method is `create_text_normalizer(voice, format)`.
It is driven by `voice.locale` for builder lookup even though **Voice** no
longer carries a locale, and it calls
`get_voice_normalization(voice.id, text_format)` without the required
`language` argument. Both latent defects are hidden by mocks and must be fixed
by keying on the passed **Language** code.

Public API becomes:

```python
def create(self, voice: Voice, text_format: TextFormat, language: str) -> TextNormalizer | None
```

`language` is a bare **Language** code (e.g. `ru`, not `ru_RU`) and is
required. It drives both the `VoiceNormalization` lookup
(`get_voice_normalization(voice.id, text_format, language)`) and the builder
registry key.

Approved design decisions (from design review — do not deviate):

- The two-level dispatch (`_factories` dict, `_create_text_normalizer_factory`,
  `_create_ssml_normalizer_factory`) collapses into a single `create` that
  branches on the `TextFormat` enum to select `settings.text` / `settings.ssml`.
  The `_builders` registry is the only dispatch table.
- Builder keys become `f"{language}__{text_format.value}__{normalization_type.value}"`
  with the existing `default__...` fallback preserved; no `voice.locale`
  anywhere. The `normalization_type` variable no longer shadows the builtin.
- Return type is `TextNormalizer | None`. Preserve all existing `None` paths:
  disabled `VoiceNormalization`, disabled default settings, no prompt found, no
  OpenAI client, and no builder match (the last still logs a warning).
- `voice is None` and `language is None` both raise `TypeError`.
- The `create_text_normalizer` name is dropped with no alias, mirroring the
  sentenizer slice (#07). Do **not** rewire the engine or other callers — that
  ride-along work belongs to the future `TtsEngineHub` migration.
- `_create_openai_normalizer` return annotation corrected to
  `TextNormalizer | None`.

Update `tests/test_text_normalizer_factory.py` to the new API: every call uses
`create(voice=..., text_format=..., language="ru")`. Fix the already-broken
imports of `SsmlNormalizationSettings` / `TextNormalizationSettings` to
`TextFormatNormalizationSettings` (a single class serves both text and ssml
now). Existing scenarios carry over unchanged, plus coverage for:
`language=None` raising `TypeError`; a language-keyed builder registry entry (or
assert the passed `language` reaches the storage lookup); and an unknown
`language` falling back to `default__...`.

## Acceptance criteria

- [x] `create(voice, text_format, language)` resolves: text+simple ->
      `PlainTextNormalizer`, ssml+simple -> `SsmlNormalizer`, text+openai with
      prompt and client -> `OpenAiTextNormalizer`
- [x] Builder lookup keys on the bare **Language** code
      (`{language}__{text_format}__{type}`) with `default__...` fallback; no
      `voice.locale` remains anywhere in the factory
- [x] `get_voice_normalization(voice.id, text_format, language)` is called with
      the passed `language` (latent bug fixed)
- [x] All five `None` paths preserved; method returns `TextNormalizer | None`
- [x] `voice=None` and `language=None` both raise `TypeError`
- [x] `_factories` and the two wrapper methods are gone; single `create`
      branches on the `TextFormat` enum
- [x] `create_text_normalizer` removed with no alias; no engine or downstream
      caller modified
- [x] `tests/test_text_normalizer_factory.py` updated to the new API with
      corrected `TextFormatNormalizationSettings` imports, incl. `None`-language
      and unknown-language-fallback coverage
- [x] Factory pytest suite passes

## Blocked by

None - can start immediately