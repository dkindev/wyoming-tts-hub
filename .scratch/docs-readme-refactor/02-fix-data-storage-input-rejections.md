---
title: "Fix the data file inputs YamlDataStorage rejects"
labels:
  - ready-for-agent
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

- [ ] Passing a `Path` works, as the type hint says it should
- [ ] A voice written with `speaker: null` either falls back to the voice name or is
      refused with an error naming it
- [ ] Both cases are covered by tests at the storage seam, and the failure mode of
      each before the fix is asserted in a test comment or commit message
- [ ] No other input the shapes allow is rejected on the way in

## Blocked by

None - can start immediately