---
title: "Prove streamed audio is unchanged on a real Model"
labels:
  - completed
created: 2026-10-15
---

## What to build

Demonstrate on a real synthesised Model that the no-copy streaming change did not alter the
audio a client receives.

This is its own ticket because the test suite mocks the Model loader throughout: every test
that exercises a TTS Engine substitutes the Silero package importer, so the suite cannot
detect a break in how a real Model's tensor becomes streamable audio. A green suite is
therefore necessary but not sufficient here.

The check must run against a Model already cached on disk, with no network access.

## Acceptance criteria

- [x] A reproducible check synthesises speech with a locally cached Model and needs no network access
- [x] The check asserts that the total streamed bytes equal sample rate × duration × bytes per sample
- [x] A Wyoming client decodes the stream, and the audio it receives matches the rate, width
      and channels announced in `AudioStart`
- [x] The exact command to re-run the check is recorded in this ticket once it exists

## Re-running the check

    pytest tests/test_real_model_stream.py -v

`tests/test_real_model_stream.py` loads `models/silero/ru/v5_5_ru.pt`, streams one
Sentence through the real storage, factory, Engine Manager, TTS Engine Hub and Wyoming
handler, and decodes the stream back as a client would. It takes about two seconds and
skips itself when no Model is cached. Downloads are blocked for its duration, so a run
that reached for the network fails rather than quietly passing on a connected machine.

The rate, width and channels a client is told are checked against the rate the Model
synthesized at and the format it publishes, not just against each other: announcing a
consistent but wrong rate fails the check.

## Notes

This check asserts the audio a client receives, so it cannot see a per-frame copy —
the same bytes leave the process either way. That stays covered by the regression test in
`02-frame-audio-without-copying.md`.

## Blocked by

- 02-frame-audio-without-copying.md