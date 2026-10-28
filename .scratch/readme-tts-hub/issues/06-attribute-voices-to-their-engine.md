---
title: "Attribute each advertised Voice to the TTS Engine that built it"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

## What to build

Every voice the server advertises is credited to Silero, whatever engine
actually produced it. The moment a second engine family is served, clients are
told a Qwen voice is Silero's work.

Let each **TTS Engine** declare where it comes from, and let the voice's
attribution follow from the **Model Info** that requested it — the same Model
Info the voice belongs to, not the server's configured default.

Each engine family carries its repository: Silero's models repository, the Qwen
TTS repository, and the OpenAI site for the OpenAI-compatible family, which has
no single upstream project to point at.

## Acceptance criteria

- [x] Each engine family carries the URL of its project
- [x] An advertised voice's attribution names its Model Info's engine family
- [x] An advertised voice's attribution URL is that engine family's URL
- [x] The attribution follows the Model Info that owns the voice, so two voices
      from different engine families are credited differently
- [x] A test at the describe seam asserts both the name and the URL, which fails
      against the hardcoded Silero attribution
- [x] The engine-family URL lives beside the family declaration, not in the
      protocol handler, so adding an engine does not mean editing the handler

## Blocked by

None (can start immediately).
## Answer

Each TTS Engine family carries its project URL in a mapping declared beside the families,
and a Voice's attribution is read from the Model Info that owns it.

**The mapping rather than tuple enum values** is a decision, not a convenience. Carrying
the URL in the value would leave `EngineType("silero")` parsing a tuple, breaking every
data file that names an engine, and the Engine Factory keys its builders on
`{engine_type}__{backend_type}`. The family values stay the bare names. A family declared
without a URL fails the suite, so the mapping cannot silently fall short — the residual
risk is a `KeyError` inside `describe`, reachable only if that test were bypassed.

**The credit tests are parametrised over every family**, which is the only form that
holds. The first version asked about Silero alone and passed against the hardcoded
`"silero"` attribution it was meant to catch — a test about the one engine the bug named
cannot detect that engine being hardcoded. Restoring the old pair now fails three tests.

The URLs themselves are pinned by value. A test comparing a Voice's credit against the
mapping only proves the handler reads it; swapping one family's URL for another's would
leave every client following the wrong link with the suite green.

**One addition beyond this ticket:** a Voice whose Model Info is absent is refused by
name rather than raising `AttributeError`. Reading `engine_type` added a second
dereference of a value typed optional, and mypy flagged it — but the crash it replaced
was already there on the next line. The guard matches the one `engine_hub.py` already
has for the same case, and lowers the suite's type errors by one rather than raising
them. It changes the Describe error a client sees from `AttributeError` to `ValueError`,
in a state `YamlDataStorage` cannot produce.

Not done, and worth knowing: the same missing-Model-Info guard now exists in two places
with the same message shape. A `DataStorage.require_model_info` would give it one policy,
and `benchmark_sample.py` still dereferences with neither.
