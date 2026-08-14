---
id: 7
title: "Refactor TextSentenizerFactory to language-keyed create()"
labels:
  - ready-for-agent
created: 2026-08-14
---

## What to build

Refactor `TextSentenizerFactory` so a caller holding a bare **Language** code — the shape the upcoming `TtsEngineHub.synthesize_pcm(..., language)` will provide — can obtain a `TextSentenizer` without any dependency on a **Voice**.

The current factory takes a `Voice` and reads `voice.locale` to pick a builder. The **Voice** no longer carries a locale, so the factory must be driven by a bare **Language** code instead (`ru`, `en`, ...), matching the **Model** declared `languages`.

Approved design decisions (from design review — do not deviate):

- Public API becomes:
  ```python
  def create(self, text_format: TextFormat, language: str | None = None) -> TextSentenizer
  ```
  (`language` is a bare language code; the parameter is optional and nullable).
- The builder registry keys on `f"{language}__{text_format.value}"`, with the previous `ru_RU` locale keys migrated to bare `ru`:
  - `default__text` → `PlainTextSentenizer`
  - `default__ssml` → `SsmlSentenizer(PlainTextSentenizer())`
  - `ru__text` → `RuPlainTextSentenizer`
  - `ru__ssml` → `SsmlSentenizer(RuPlainTextSentenizer())`
- Lookup falls back from `f"{language}__{text_format.value}"` to `f"default__{text_format.value}"` when the language has no registered builder or is `None`. This graceful default fallback is the intended behavior — unknown languages (e.g. `en`) use the generic plain-text sentenizer.
- The return type is non-optional `TextSentenizer`: remove the dead `return None` path and the legacy `voice is None` guard. Guard the (unreachable, since `default__{text_format}` is always registered) residual no-builder branch by raising `ValueError`.
- The registry annotation is `Callable[[], TextSentenizer]` (the old annotation claimed `type[TextSentenizer]` while also storing lambdas).

Add direct unit coverage for the factory (none exists today): default text/SSML resolution, `ru` resolution for both text and SSML (including the inner plain sentenizer type), unknown-language and `None` fallback, and that each call returns a fresh, usable instance.

Scope boundary: do **not** rewire the engine to the new method or touch the normalizer factory or callers — those ride along with the future `TtsEngineHub` migration. This slice stands on its own.

## Acceptance criteria

- [x] `TextSentenizerFactory.create(text_format, language=None)` resolves `ru` text to `RuPlainTextSentenizer` and `ru` SSML to a `SsmlSentenizer` wrapping `RuPlainTextSentenizer`
- [x] Unknown languages and `language=None` fall back to the `default__*` builders (`PlainTextSentenizer` / `SsmlSentenizer(PlainTextSentenizer())`)
- [x] `create` returns a non-optional `TextSentenizer` for every `TextFormat`; no `None` return path and no `Voice` coupling remain
- [x] The registry uses `Callable[[], TextSentenizer]` typing and bare-language keys (no `ru_RU` locale keys)
- [x] New factory unit tests cover default, ru, unknown-language, `None`, and fresh-instance cases and all pass
- [x] No engine, normalizer factory, or downstream caller is modified

## Blocked by

None - can start immediately