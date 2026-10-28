---
title: "Fix the data file inputs YamlDataStorage rejects"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

Two ways of writing a data file that the **Model Info** and **Voice** shapes allow
crash the server at startup, instead of being read as written.

**A path given as a `Path` object.** `YamlDataStorage` declares
`config_path_or_model: str | Path | PredefinedData` and then calls `strip()` on what
it was handed, so passing a `Path` — exactly what the type hint invites — raises
`AttributeError: 'PosixPath' object has no attribute 'strip'`.

**A voice whose `speaker` is `null`.** A voice with no speaker is meant to fall back
to the voice name, and it does when the key is absent. Written as `speaker: null`
it raises instead, because the fallback reaches `strip()` on `None`. Either treat an
explicit null like an absent key, or reject it with a message naming the voice.

## Acceptance criteria

- [x] Passing a `Path` works, as the type hint says it should
- [x] A voice written with `speaker: null` either falls back to the voice name or is
      refused with an error naming it
- [x] Both cases are covered by tests at the storage seam, and the failure mode of
      each before the fix is asserted in a test comment or commit message
- [x] No other input the shapes allow is rejected on the way in

## Answer

Both named cases are fixed, and each test's docstring records what it did before.

**A `Path`** is read as written. Every existing test hands over a string, which is why
nothing caught it.

**`speaker: null`** falls back to the voice name, the same as an absent key — which is
how `ref_audio`, `ref_text` and `instruct` already treat one.

The fourth criterion turned out to be most of the work. Every one of these raised a
bare `AttributeError`, `TypeError` or `KeyError` from inside the parser, naming
nothing about the file that was wrong:

- `models:`, `voices:`, `prompts:` written as null, or as the wrong kind of thing
- a model with no body, a voice entry that is null or not a mapping, a prompt that is
  null or missing `id`, `text` or `model`
- `languages: ru` — read as the characters `['r', 'u']` — and a language that is not
  a string
- `name: null`, which became a voice named `None`
- `normalization` written as something other than a mapping, or per language as
  something other than a mapping, both of which were dropped in silence

Each is now refused with a message naming the file, the **Model Info**, the **Voice**
or the entry, in the voice of the messages already there. Silent misreads were the
worst of them: an override the reader wrote and the server never read.

Parsing the model and the voice out of the load loop into their own methods was
needed to keep the function within the complexity limit ruff enforces, and left the
loop reading as a list of what it holds.

## Blocked by

None - can start immediately