---
title: "Attribute each advertised Voice to the TTS Engine that built it"
labels:
  - ready-for-agent
created: 2026-10-18
---

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

- [ ] Each engine family carries the URL of its project
- [ ] An advertised voice's attribution names its Model Info's engine family
- [ ] An advertised voice's attribution URL is that engine family's URL
- [ ] The attribution follows the Model Info that owns the voice, so two voices
      from different engine families are credited differently
- [ ] A test at the describe seam asserts both the name and the URL, which fails
      against the hardcoded Silero attribution
- [ ] The engine-family URL lives beside the family declaration, not in the
      protocol handler, so adding an engine does not mean editing the handler

## Blocked by

None (can start immediately).