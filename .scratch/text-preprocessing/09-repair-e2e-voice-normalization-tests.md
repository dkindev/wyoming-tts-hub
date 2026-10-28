---
id: 9
title: "Repair e2e voice-normalization tests against real storage"
labels:
  - ready-for-agent
created: 2026-08-14
---

## What to build

Rewrite `tests/test_voice_normalization_e2e.py` so it exercises
`TextNormalizerFactory.create(voice, text_format, language)` end-to-end through
a real `YamlDataStorage`. Today every test in the file fails before the factory
is even reached: the YAML fixtures use a pre-refactor schema that the current
parser rejects (e.g. `Model 'v5_5_ru' is missing required 'engine_type'`).

The fixtures must be rewritten to the current config schema, as an agent
confidence test of `create` plus storage parsing. Illustrative shape (encoded
decisions, adjust to match `YamlDataStorage` exactly):

```yaml
models:
  v5_5_ru:
    engine_type: silero
    languages: [ru]
    voices:
      - name: aidar
        normalization:
          ru:
            text:
              enabled: true
              type: openai
              prompt_id: ru_text
```

Key consequences to honor:

- Voice ids are now `{model_id}-{voice_name}` (`v5_5_ru-aidar`), not the old
  `ru_RU-v5_5_ru-aidar` — `helpers.make_voice` must receive a matching id.
- The `language` dimension sits inside `normalization` (`ru:` key), and the
  factory call passes that bare code: `create(voice, text_format=TextFormat.TEXT, language="ru")`.
- Default `TextFormatNormalizationSettings.enabled` is `False`
  (`src/config.py`). The "no normalization falls through to system default"
  test therefore must construct
  `NormalizationSettings(text=TextFormatNormalizationSettings(enabled=True))`
  (type defaults to `SIMPLE`) so it expects `PlainTextNormalizer`. The
  voice-normalization override cases work with default settings since the
  `VoiceNormalization` wins.

Verify the same three scenarios that exist today: LLM normalization ->
`OpenAiTextNormalizer`, `enabled: false` -> `None`, and no normalization ->
`PlainTextNormalizer`.

## Acceptance criteria

- [ ] LLM fixture (current schema) + `create(..., language="ru")` through real
      `YamlDataStorage` returns `OpenAiTextNormalizer`
- [ ] `enabled: false` fixture returns `None`
- [ ] No-normalization voice with text normalization explicitly enabled in
      settings returns `PlainTextNormalizer`
- [ ] Fixtures use the current YAML schema and `{model_id}-{voice_name}` ids;
      no pre-refactor `locales`/`language:` structure remains
- [ ] All three e2e tests pass via `TextNormalizerFactory.create` (new API)

## Blocked by

- #8 — `TextNormalizerFactory` must expose the new `create(voice, text_format, language)` API