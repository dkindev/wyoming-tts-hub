---
title: "Text normalization and Sentence splitting run as Hub middleware"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

The Engine Hub redesign moved Text normalization and Sentence splitting out of
the synthesis engine and into a middleware chain that runs before the request
reaches a TTS Engine. This is now the only place those steps happen, and it is
untested.

Deliver coverage of the chain as a whole, plus the individual middlewares:

**Sentence splitting.** Text longer than the configured maximum Sentence length
reaches the TTS Engine as several Sentences, and the engine is invoked once per
Sentence. Text within the limit reaches the engine as a single Sentence.

**Language.** A Voice with a VoiceNormalization override for a Language and Text
Format routes through that override's normalizer type. A Voice without an
override falls through to the server-wide default. An override marked disabled
means no normalization at all for that Voice, Text Format, and Language
combination — even when the server-wide default is enabled.

**Normalization.** When a normalizer is selected, it is applied to every Sentence.
When none is selected, the Sentences pass through untouched. A Voice that
references a Prompt the storage cannot resolve yields no normalizer rather than
a broken one.

**Failure.** A Voice whose Language and Text Format have no registered
sentence splitter is an error naming both, so the misconfiguration is
diagnosable from the log.

Also cover the language-detection step, which currently assigns a fixed Language
rather than detecting one. Cover the behaviour as it is today — a Language is
assigned to every request — and note the limitation, since it is specified
differently (see ticket 09).

## Acceptance criteria

- [x] Text within the maximum Sentence length produces exactly one engine
      invocation
- [x] Text exceeding it produces one engine invocation per Sentence, each
      carrying its own Sentence
- [x] A Voice with a VoiceNormalization override uses the override's normalizer
      type; a Voice without one uses the server-wide default
- [x] A Voice whose override is disabled gets no normalization despite an enabled
      server-wide default
- [~] An override referencing an unresolvable Prompt yields no normalizer
      — **divergence:** the factory falls back to the server-wide default Prompt for
      the Language instead. Both branches are pinned by tests; the ticket's wording
      needs a decision on which is intended.
- [x] A missing sentence splitter for a Language and Text Format raises an error
      naming both the Voice and the Language
- [x] The selected normalizer is applied to every Sentence

## Blocked by

- [03: Engine Hub routes a Voice to its Model and frames the audio](03-engine-hub-routing-and-framing.md)