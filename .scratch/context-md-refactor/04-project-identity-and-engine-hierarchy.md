---
title: "Slice 4: Project identity + Engine/Hub/Model hierarchy"
labels:
  - ready-for-agent
created: 2026-08-11
---

## What to build

Rework the CONTEXT.md project identity to reflect the multi-engine future and introduce the engine hierarchy that everything else hangs off. This slice changes only the overview, the top three domain terms, their relationships, and the new "TTS model" ambiguity entry. Later slices add the Model-capability and voice-layer terms (Language, Text Format, Speaker, Voice) and the pipeline/relationships/polish, so do not touch those terms here.

Apply to `CONTEXT.md`:

1. **Title** — change the H1 to `Wyoming TTS Hub — Domain Context`.

2. **Overview** — replace the current two sentences with:

   > A simple, robust, and performant **Wyoming protocol TTS server** built around a
   > **TTS Engine Hub** that aggregates multiple **TTS Engines** (e.g., Silero,
   > Qwen3-tts, OpenAI-compatible APIs). Provides text-to-speech generation over TCP
   > using the Wyoming protocol, enabling integration with Home Assistant and other
   > Wyoming clients.

3. **TTS Engine** — redefine (drop the Silero reference; an engine is one provider family that owns Models):

   > A backend that synthesizes speech from text input for one provider family (e.g.,
   > Silero, Qwen3-tts, an OpenAI-compatible API). Owns one or more **Models** and
   > produces raw PCM audio output.
   > _Avoid_: Speech generator, voice synthesizer

4. **TTS Engine Hub** — add as a new term:

   > The top-level component that aggregates **TTS Engines**. Routes each synthesis
   > request to the engine that owns the requested **Model**, splits text into
   > **Sentences**, and applies **Text normalization**. Coordinates warmup and
   > shutdown across engines.
   > _Avoid_: TTS server, orchestrator

5. **Model** — redefine (belongs to exactly one engine):

   > A named, language-specific model that belongs to exactly one **TTS Engine**.
   > Models can be enabled, disabled, or pre-warmed at startup. Each model supports
   > one or more speakers.
   > _Avoid_: Neural network, PyTorch model

6. **Relationships** — add these lines (the existing Model→Speaker and Voice-related lines stay; later slices expand this section):

   - A **TTS Engine Hub** aggregates one or more **TTS Engines**
   - A **TTS Engine** owns one or more **Models**
   - A **Model** belongs to exactly one **TTS Engine**

7. **Flagged ambiguities** — add:

   - "TTS model" was used to mean both a provider family (Silero, Qwen3-tts, an
     OpenAI-compatible API) and a specific named model — resolved: a provider
     family is a **TTS Engine**; a specific named model is a **Model**

Keep the existing term definitions for Language-related wording out of scope; do not introduce Language, Text Format, Speaker, or Voice changes in this slice. Do not edit README.md or AGENTS.md.

## Acceptance criteria

- [x] CONTEXT.md H1 is `Wyoming TTS Hub — Domain Context`
- [x] Overview describes a hub aggregating multiple TTS Engines (Silero, Qwen3-tts, OpenAI-compatible APIs) and no longer says it "wraps the Silero TTS engine"
- [x] TTS Engine is defined as one provider family owning one or more Models, with `_Avoid_` aliases
- [x] TTS Engine Hub is defined as the aggregator that routes by Model and coordinates warmup/shutdown, with `_Avoid_` aliases
- [x] Model is defined as belonging to exactly one TTS Engine
- [x] Relationships include Hub aggregates Engines, Engine owns Models, Model belongs to exactly one Engine
- [x] Flagged ambiguities includes the "TTS model" → Engine vs Model resolution
- [x] No Language, Text Format, Speaker, or Voice terms were changed in this slice

## Blocked by

None — can start immediately
