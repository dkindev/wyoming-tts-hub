---
title: "Domain language for Voice Prompt and Reference Audio, and the model-download decision"
labels:
  - completed
created: 2026-10-19
---

## What to build

Two new concepts have entered the domain, and one architectural decision was
made while adding the engine. Record both so the next contributor and agent use
the same words and understand why checkpoints land where they do.

Add **Voice Prompt** — the model-side conditioning built from a Voice's
Reference Audio — and **Reference Audio** to the glossary. Disambiguate Voice
Prompt from the existing Prompt, which is an LLM prompt: this codebase now has
two unrelated things called a prompt, and the glossary exists to stop exactly
that confusion.

Record the decision to fetch upstream checkpoints into the Models directory
rather than a shared global model cache, together with the trade-off that
motivated it: operators control and can back up the model directory, and an
offline deployment keeps working, at the cost of not sharing a cache with other
tools.

## Acceptance criteria

- [x] The glossary defines Voice Prompt and Reference Audio in the repo's glossary format
- [x] The existing Prompt entry disambiguates against Voice Prompt
- [x] Definitions are one or two sentences, opinionated, and name avoided synonyms
- [x] One ADR records fetching upstream checkpoints into the Models directory, following the ADR format
- [x] The glossary contains no implementation detail

## Blocked by

- [04: Qwen3-TTS voice cloning end to end](04-qwen3-tts-voice-cloning-end-to-end.md)
