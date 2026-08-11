---
title: "Slice 6: Pipeline terms, full Relationships, example dialogue, de-Silero polish"
labels:
  - ready-for-agent
created: 2026-08-11
---

## What to build

Finish the CONTEXT.md multi-engine refactor: attribute the preprocessing pipeline to the TTS Engine Hub, complete the Relationships section, replace the example dialogue, and run a polish pass that removes every remaining Silero-only reference. Builds on Slices 4 and 5 (engine hierarchy and Model-capability terms).

Apply to `CONTEXT.md`:

1. **Sentence** — attribute the splitting to the Hub:

   > A segment of text split from the input by the **TTS Engine Hub** to stay within
   > model length limits. Multiple Sentences are synthesized separately and streamed
   > as a single audio response.
   > _Avoid_: Segment, fragment

2. **Text normalization** — attribute the step to the Hub:

   > The preprocessing step applied by the **TTS Engine Hub** to text before TTS
   > synthesis that ensures clean input by stripping whitespace and removing
   > characters unavailable in the active model.
   > _Avoid_: Preprocessing, text cleaning, normalization (alone)

3. **VoiceNormalization** — make the per-format/per-language references use the now-defined terms:

   > A per-voice, per-**Text Format**, per-**Language** override of normalization
   > settings. Links a voice to a specific normalization type (simple or openai) for
   > a bare **Language** code, optionally referencing a reusable prompt. When
   > present, it overrides the server-wide default for that voice, **Text Format**,
   > and **Language** combination.
   > _Avoid_: Normalization override, voice normalisation config

4. **Relationships** — replace the entire section with (do not drop any line from Slices 4 and 5):

   - A **TTS Engine Hub** aggregates one or more **TTS Engines**
   - A **TTS Engine** owns one or more **Models**
   - A **Model** belongs to exactly one **TTS Engine**
   - A **Model** supports one or more **Speakers** and one or more **Languages**
   - A **Speaker** belongs to exactly one **Model**
   - A **Speaker** within a **Model** may be referenced by one or more **Voices**
   - A **Voice** references exactly one **Model** and either exactly one **Speaker**
     or engine-specific reference parameters; the language of its speech is
     derived from the **Model**
   - The **TTS Engine Hub** splits text into **Sentences**, applies **Text
     normalization** to each **Sentence**, then routes the normalized **Sentences**
     to the **TTS Engine** that owns the requested **Model**
   - A **TTS Engine** synthesizes each **Sentence** into one or more **Chunks**,
     which the server streams over the Wyoming protocol
   - The server advertises supported **Voices**, plus per-**Model** **Languages**
     and **Text Formats**, over the **Wyoming** protocol
   - A **Voice** has zero or more **VoiceNormalizations** (per **Text Format** and
     **Language** overrides)
   - A **Prompt** is referenced by zero or more **VoiceNormalizations**

5. **Example dialogue** — replace with one that demonstrates Hub routing and multi-engine behavior:

   > **Dev:** "If I configure a **Voice** `v5_5_ru-aidar` backed by model
   > `v5_5_ru` under the Silero **TTS Engine**, does the **TTS Engine Hub** load
   > the model immediately?"
   > **Domain expert:** "No — the **Model** is only loaded when the first synthesis
   > request for it arrives, unless its `warmup` is set to `true`."
   > **Dev:** "How does the **TTS Engine Hub** pick an engine?"
   > **Domain expert:** "Each **Model** belongs to exactly one **TTS Engine**. The
   > Hub routes by **Model**, then splits the text into **Sentences** and applies
   > **Text normalization** before handing them to the engine."
   > **Dev:** "Can two voices share one speaker?"
   > **Domain expert:** "Yes — a **Voice** is a preset anchored to a
   > **(Model, Speaker)** pair. `aidar-soft` and `aidar-loud` under `v5_5_ru` can
   > both map to `speaker: aidar`."
   > **Dev:** "What if a Wyoming client selects a voice by language instead of by
   > name?"
   > **Domain expert:** "The **TTS Engine Hub** matches a **Voice** against the
   > **Model**'s supported **Languages**."
   > **Dev:** "Does every model support SSML?"
   > **Domain expert:** "No — the **TTS Engine Hub** advertises the **Text
   > Formats** each **Model** supports; some engines only accept plain text."

6. **Flagged ambiguities** — ensure both entries are present:

   - "Model" was used to mean both a config entry and the loaded neural network —
     resolved: **Model** is a configuration concept
   - "TTS model" was used to mean both a provider family (Silero, Qwen3-tts, an
     OpenAI-compatible API) and a specific named model — resolved: a provider
     family is a **TTS Engine**; a specific named model is a **Model**

7. **Polish pass** — the finished file must satisfy:
   - Every term has an `_Avoid_` line
   - Every term participates in at least one relationship
   - No Silero reference remains except as an example engine (overview, TTS Engine term, Speaker example, dialogue)
   - The **Chunk** term ("Raw PCM audio bytes produced by the **TTS Engine** for streaming over the Wyoming protocol") is unchanged
   - The **Prompt** term is unchanged

## Acceptance criteria

- [x] Sentence and Text normalization are attributed to the TTS Engine Hub
- [x] VoiceNormalization references the **Text Format** and **Language** terms
- [x] Relationships section contains all 12 lines listed above
- [x] Example dialogue demonstrates engine routing, language-based voice selection, and per-Model Text Formats
- [x] Flagged ambiguities lists both the "Model" and "TTS model" entries
- [x] Every term has an `_Avoid_` alias and participates in a relationship
- [x] No Silero references remain except as an example engine; Chunk and Prompt are unchanged

## Blocked by

- Slice 5: Model capabilities (Language, Text Format) + Speaker/Voice layer
