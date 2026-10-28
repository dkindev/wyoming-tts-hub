---
title: "The Hub rejects a Language the Model does not declare"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## Notes

Landed as `tests/test_engine_hub.py::TestLanguageValidation::test_language_the_model_does_not_declare_is_rejected`,
which fails against current source with `DID NOT RAISE ValueError` while the log
shows the engine synthesizing the text anyway. The disagreement between the
domain context and the implementation, and the open question of whether detection
is wanted at all, are recorded in
[12-language-never-validated-against-model.md](12-language-never-validated-against-model.md).

## What to build

**This ticket lands a failing test.** It documents a gap between the specified
and implemented behaviour rather than closing it. No production code changes here.

The domain context specifies that a Wyoming client *may* send a Language with a
synthesis request, and that when it does the TTS Engine Hub validates it against
the selected Model's declared Languages and rejects the request on a mismatch.
It further specifies that when the client omits a Language, the Hub resolves it
from the Model's sole declared Language, falling back to auto-detection for
Models that declare it.

Neither happens. The Language is accepted as given and passed straight to the
engine, and the language-detection middleware assigns a fixed value to every
request rather than detecting anything. So a client asking for a Language the
Model cannot speak gets audio synthesized in the wrong language, with no error.

Write the test that pins the specified behaviour: a request carrying a Language
the Model does not declare is rejected, and the error names both the Language and
the Model's declared Languages so the caller can correct it.

It will fail against current source. File the accompanying issue recording that
the domain context and the implementation disagree, so a human can decide
between implementing validation and amending the domain context.

Note for whoever picks this up: detection is a separate question from validation
and is deliberately out of scope here. The domain context says an omitted
Language resolves from the Model's sole declared Language before falling back to
detection, and the current fixed-value middleware satisfies neither reading.
Deciding whether detection is even wanted, given Models already declare their
Languages, is a design call that should be made explicitly rather than inferred.

## Acceptance criteria

- [x] A test requests a Language the Model does not declare and asserts the
      request is rejected
- [x] The rejection names the requested Language and the Model's declared
      Languages
- [x] The test currently fails, and the failure demonstrates the missing
      validation rather than an unrelated error
- [x] No production code is changed by this ticket
- [x] An accompanying issue records the disagreement between the domain context
      and the implementation, and flags detection as an open design question

## Blocked by

- [03: Engine Hub routes a Voice to its Model and frames the audio](03-engine-hub-routing-and-framing.md)