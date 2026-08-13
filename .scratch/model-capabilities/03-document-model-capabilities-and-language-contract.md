---
title: "Document Model capabilities and the optional-language contract in CONTEXT.md"
labels:
  - ready-for-agent
created: 2026-08-13
---

## What to build

Update the domain context (`CONTEXT.md`) to match the resolved design for
**Model** capabilities and the Wyoming **Language** contract. The wording was
settled in a design-grilling session; implement it as written.

Changes:

- **Model** entry: document that a Model declares its `engine_type`, its
  supported **Languages**, whether it auto-detects its language
  (`language_auto_detected`), and whether it accepts **SSML**
  (`ssml_supported`).
- **Language** entry: replace the outdated "clients select a voice by Language
  when not specifying a name" with the optional-language contract — a Wyoming
  client *may* send a **Language**; when sent, the **TTS Engine Hub** validates
  it against the selected **Model**'s declared **Languages** and rejects the
  request on a mismatch; when omitted, the Hub resolves it from the **Model**'s
  sole declared **Language**, falling back to auto-detection.
- **Text Format** entry: note that a **Model**'s support for `ssml` is declared
  via `ssml_supported`.
- **Example dialogue**: replace the outdated "select a voice by language instead
  of by name" exchange with the optional-language resolution contract.

## Acceptance criteria

- [x] `Model` entry documents `engine_type`, `languages`, `language_auto_detected`, `ssml_supported`
- [x] `Language` entry reflects the optional-language resolution contract (no stale "when not specifying a name" wording)
- [x] `Text Format` entry references per-Model `ssml_supported`
- [x] Example dialogue updated; no stale "select by language instead of by name" wording remains

## Blocked by

- model-capabilities/01-add-engine-type-and-language-capabilities-to-model
