---
title: "Describe the package as the TTS Engine Hub it is"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

## What to build

A client asking what this server is, and who to credit, is told it wraps the
Silero TTS engine and is credited to the distribution name — both left over from
before the hub existed, and both read straight out of the package metadata into
the Wyoming protocol's own program description.

Fix the metadata at its source so the protocol answer and every place the package
is described follow from it.

## Acceptance criteria

- [x] The package summary describes a TTS Engine Hub aggregating TTS Engines,
      and no longer describes a server that wraps Silero
- [x] The Wyoming program description a client receives is that summary
- [x] The program's attribution names the project rather than the stale
      distribution name
- [x] The repository's own description and keywords name the hub and the engine
      families it aggregates
- [x] A test asserts the description served over the protocol is not the
      Silero-wrapping summary

## Blocked by

None (can start immediately).
## Answer

The summary now describes a TTS Engine Hub aggregating TTS Engines, and the keywords
name the hub and the one engine family actually aggregated. `qwen` and `openai` are left
out of both: they are declared families with no engine behind them, and `openai` names a
normalization client rather than an engine, so listing them would advertise what the
project does not do.

**Credit is not the service name.** The first attempt reused `settings.app_name` for the
attribution, and the test that appeared to cover it was a tautology — it compared the
attribution against the same constant it passed to the handler, so reverting the wiring
would have left it green. Both were wrong together: an operator naming their service
"Kitchen Speaker" would have made the server claim credit as "Kitchen Speaker".

There is now a third name. `PROJECT_NAME` is what the project calls itself, the service
name is what a deployment is called, and the distribution name is what it is packaged as.
The attribution names the first; the protocol name is the second; the distribution name
is what it used to use for credit and is not a project identity at all. The tests pin
all three apart, and both plausible regressions — crediting the service name, or crediting
the distribution name — now fail.

**The description is read from the installed distribution, not from `pyproject.toml`,** so
editing the summary without reinstalling would leave a client being told something the
project no longer says, with nothing failing. That is what happened while writing this:
the served description stayed stale until the distribution was reinstalled. A test now
compares the two directly, and fails until they agree.

The negative assertion — that the summary no longer claims to wrap Silero — is kept in
one place, where the string is authored, rather than repeated at the wire. Pinning the
absence of a phrase in two places guards nothing the positive assertion does not, and the
phrase could be reworded out of a negative check while keeping the same meaning.
