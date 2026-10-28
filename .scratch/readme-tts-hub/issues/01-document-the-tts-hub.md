---
title: "Document the server as the Wyoming TTS Hub"
labels:
  - ready-for-agent
created: 2026-10-18
---

## What to build

The README still introduces the project as a Silero-specific server, so a reader
arriving after the Wyoming TTS Hub migration is told the wrong thing about what
the project is, which TTS Engines it can serve, what audio a client actually
receives, and what a voice is called on the wire.

Bring the README in line with what the server does now. Everything a reader needs
in order to run it, configure it, and point a client at it must be true, and the
model, voice and normalization documentation must survive the rewrite untouched.

Changes:

- The H1 becomes the product name the glossary and the configured application
  name already use, and the opening line describes the server in the glossary's
  vocabulary — a **TTS Engine Hub** routing each request to the **TTS Engine**
  that owns the requested **Model Info**. It keeps the three claims that are
  still true: Home Assistant integration, streaming audio, and optional
  per-voice LLM normalization. It stops presenting Silero as the project's
  identity.
- Under the models documentation, state plainly which engine family is
  implemented. Silero on the torch backend is the only pairing that builds an
  engine; the other declared families are accepted in configuration and then
  rejected at startup with an error naming the family and the backend. Say so,
  so nobody writes a configuration the server refuses to start on. Leave the
  field table itself as it stands.
- Rename the Docker image tag to match the product. Nothing publishes an image,
  so the tag is a convention the README owns.
- Keep the clone URL truthful rather than aspirational. The repository and the
  distribution are both still named after Silero; renaming them is separate
  work, and this ticket is not it.
- Add a "Connecting a client" subsection at the end of Quick Start. It covers
  what a client sees: voice ids built as the Model Info's id then the voice's
  name, the zeroconf name the server advertises, the fact that only the voices
  of **Active Model Infos** are offered, the existing HTTP test-server command
  moved down from the numbered install steps, and the rule that decides whether
  a client is told what actually went wrong or only that something did.
- Correct the audio output. The configured sample rate is not the rate a client
  receives: the server emits the nearest rate the Model Info's TTS Engine
  supports, and announces that rate in its audio-start event. Format, bit depth
  and channel count are correct and stay.

Constraint: the models, voices and voice-normalization sections, their tables
and their YAML examples are preserved byte for byte. Automated tests parse the
README and require those three headings by exact name, check the field names in
their tables against the shapes the code has, and load the YAML examples as a
data file — so their names, their field sets and their contents cannot change
in this ticket.

## Acceptance criteria

- [x] The README's title and opening line name the TTS Engine Hub and use the
      glossary's vocabulary
- [x] The opening line still claims Home Assistant integration, streaming audio
      and optional per-voice LLM normalization, and no longer claims the project
      wraps Silero as its identity
- [x] A reader is told which engine family is implemented and that the others
      are refused at startup
- [x] The Docker build and run commands use an image tag matching the product
      name
- [x] The clone URL resolves to the repository the project is actually in
- [x] A "Connecting a client" subsection explains voice ids, zeroconf
      discovery, which voices are advertised, how error detail is governed, and
      shows the HTTP test-server command
- [x] The audio section states that the announced sample rate is the nearest one
      the Model Info's TTS Engine supports, not the configured one
- [x] The models, voices and voice-normalization sections, their tables and
      their YAML examples are unchanged
- [x] The README tests that parse and load it pass unchanged

## Blocked by

None (can start immediately).