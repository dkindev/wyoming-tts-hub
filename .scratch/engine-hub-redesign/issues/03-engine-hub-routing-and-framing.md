---
title: "Engine Hub routes a Voice to its Model and frames the audio"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

The TTS Engine Hub is the entry point for every synthesis request after the
redesign, and it has no tests at all. A caller asks the Hub for a Voice by id and
gets audio back, framed for streaming.

This ticket establishes the tracer bullet through the redesigned request path:
resolve the Voice, resolve the Model that owns it, run the middleware chain, and
emit the resulting audio as frames sized to the configured frame duration. Later
tickets hang off this one.

Deliver:

- A successful synthesis for a known Voice, with no middleware configured,
  yields audio chunks whose total length matches the engine's output.
- Each emitted frame carries the right sample rate, bytes per sample, and
  channel count for the Wyoming protocol, and is sized to the configured frame
  duration.
- Text that is empty or only whitespace is rejected.
- An unknown Voice is rejected, naming the Voice.
- A Voice whose Model cannot be resolved is rejected, naming the Model.

Use a fake TTS Engine and a fake Engine Manager so this ticket tests the Hub's
own logic rather than any particular engine.

## Acceptance criteria

- [x] Synthesizing a known Voice yields one or more chunks whose concatenated
      audio equals the fake engine's output
- [x] Every chunk reports two bytes per sample and one channel, and carries the
      sample rate the engine produced
- [x] Frame size matches the configured frame duration
- [x] Empty or whitespace-only text raises an error naming the empty text
- [x] An unknown Voice raises an error naming that Voice
- [x] A Voice whose Model is missing raises an error naming that Model
- [x] The tests exercise the Hub through its public entry point, without
      reaching into private state

## Blocked by

- [01: Restore a runnable test suite](01-restore-runnable-test-suite.md)