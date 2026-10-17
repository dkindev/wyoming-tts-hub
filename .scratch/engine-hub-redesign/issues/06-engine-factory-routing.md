---
title: "Engine Factory resolves a Model to its TTS Engine family"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

Every Model declares which TTS Engine family owns it. The Engine Factory is the
seam that turns that declaration into a constructed TTS Engine, and it currently
has no tests.

Deliver:

- A Silero Model on the torch backend yields a Silero TTS Engine configured from
  the server settings — device, sample rate, Models directory, and registry URL.
- A Model family with no registered engine for the requested backend is rejected,
  naming both the family and the backend so the operator can see which combination
  is missing.
- Requesting an engine for a missing Model is a type error rather than a lookup
  failure deep inside the family.

Only the Silero-on-torch pairing is implemented today; the Qwen and
OpenAI-compatible families are declared in the domain vocabulary but have no
engine behind them yet. Cover the declared-but-unimplemented families as
rejections, so registering one later is a visible change rather than a silent one.

## Acceptance criteria

- [x] A Silero Model on the torch backend yields a Silero TTS Engine
- [x] The constructed engine carries the configured device, sample rate, Models
      directory, and registry URL
- [x] A Model declaring a family with no registered engine is rejected with an
      error naming both the family and the backend
- [x] The Qwen and OpenAI families are rejected today as unimplemented
- [x] A missing Model is a type error

## Blocked by

- [01: Restore a runnable test suite](01-restore-runnable-test-suite.md)