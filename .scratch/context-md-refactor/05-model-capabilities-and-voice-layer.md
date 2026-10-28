---
title: "Slice 5: Model capabilities (Language, Text Format) + Speaker/Voice layer"
labels:
  - ready-for-agent
created: 2026-08-11
---

## What to build

Add the two per-Model capability terms (Language, Text Format) and rework the Speaker and Voice terms for a multi-engine world, after Slice 4's engine hierarchy is in place. This slice touches only those four terms plus the Relationships lines that connect them to Model; it does not touch Sentence, Text normalization, VoiceNormalization, or Prompt (those come in Slice 6).

Apply to `CONTEXT.md`:

1. **Language** — add as a new term:

   > A spoken-language code (e.g., `ru`, `en`) that a **Model** supports. The **TTS
   > Engine Hub** advertises supported **Languages** per **Model**, and Wyoming
   > clients select a voice by **Language** when not specifying a name.
   > _Avoid_: locale, locale string

2. **Text Format** — add as a new term:

   > The input format a **TTS Engine** accepts for a **Model** during synthesis —
   > either `text` or `ssml`. Not every **Model** supports every format, so the
   > **TTS Engine Hub** advertises the supported **Text Formats** per **Model**.
   > _Avoid_: format, text type

3. **Speaker** — redefine to drop the Silero reference and make the concept universal:

   > The engine-level voice profile within a **Model** that the owning **TTS Engine**
   > selects during synthesis (e.g., a Silero speaker like `aidar`, or an OpenAI
   > voice name like `alloy`). Speakers are model-specific — the same speaker name
   > may refer to different profiles across different models. One or more **Voices**
   > can map to the same **Speaker**.
   > _Avoid_: Voice (when meaning a speaker profile)

4. **Voice** — generalize: a voice is anchored to a Model plus engine-specific parameters, not always a Speaker:

   > A user-facing preset that references exactly one **Model** and the
   > engine-specific parameters needed to synthesize its speech — a **Speaker**
   > within that **Model**, or reference audio/text for cloning-style engines.
   > Multiple **Voices** can map to the same **Speaker** within a **Model**.
   > _Avoid_: Speaker (when meaning a named voice)

5. **Relationships** — add these lines:

   - A **Model** supports one or more **Speakers** and one or more **Languages**
   - A **Voice** references exactly one **Model** and either exactly one **Speaker**
     or engine-specific reference parameters; the language of its speech is
     derived from the **Model**

   Keep the existing "A Speaker belongs to exactly one Model" and "A Speaker within a Model may be referenced by one or more Voices" lines.

## Acceptance criteria

- [x] Language is defined as a per-Model spoken-language code, with `_Avoid_`: locale, locale string
- [x] Text Format is defined as the `text`/`ssml` input format per Model, with `_Avoid_`: format, text type
- [x] Speaker is redefined without Silero and notes OpenAI voice names map to the speaker profile
- [x] Voice is generalized to reference exactly one Model plus a Speaker or reference audio/text for cloning-style engines
- [x] Relationships include Model supports Languages, Model supports Speakers, and the generalized Voice→Model relationship
- [x] Existing Speaker→Model and Speaker→Voices lines are preserved
- [x] Sentence, Text normalization, VoiceNormalization, and Prompt terms were not changed in this slice

## Blocked by

- Slice 4: Project identity + Engine/Hub/Model hierarchy
