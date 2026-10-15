# Wyoming TTS Hub — Domain Context

A simple, robust, and performant **Wyoming protocol TTS server** built around a
**TTS Engine Hub** that aggregates multiple **TTS Engines** (e.g., Silero,
Qwen3-tts, OpenAI-compatible APIs). Provides text-to-speech generation over TCP
using the Wyoming protocol, enabling integration with Home Assistant and other
Wyoming clients.

## Language

**TTS Engine Hub**:
The top-level component that aggregates **TTS Engines**. Routes each synthesis
request to the engine that owns the requested **Model**, splits text into
**Sentences**, and applies **Text normalization**. Coordinates warmup and
shutdown across engines.
_Avoid_: TTS server, orchestrator

**TTS Engine**:
A backend that synthesizes speech from text input for one provider family (e.g.,
Silero, Qwen3-tts, an OpenAI-compatible API). Produces raw PCM audio output. That audio
is streamed as **Frames** read from the **Chunk** it arrived in, so a **TTS Engine** must
treat a **Chunk** it has yielded as handed over — see **Chunk**.
_Avoid_: Speech generator, voice synthesizer

**Model**:
A named, language-specific model that belongs to exactly one **TTS Engine**.
Models can be enabled, disabled, or pre-warmed at startup. A **Model** declares its `engine_type` (which **TTS
Engine** family owns it), the **Languages** it supports, whether it may be
asked to synthesize without one (`language_auto_detected`), and whether it accepts
**SSML** (`ssml_supported`). The declared **Languages** are the source of truth
advertised for the **Model**'s **Voices**.
_Avoid_: Neural network, PyTorch model

**Language**:
A spoken-language code (e.g., `ru`, `en`) that a **Model** declares it
supports. A Wyoming client *may* send a **Language** with a synthesis request;
when sent, the **TTS Engine Hub** validates it against the selected **Model**'s
declared **Languages** and rejects the request on a mismatch. When omitted, the
Hub fills it in from the **Model**'s sole declared **Language** — but only when
the **Model** declares exactly one **Language** and does not auto-detect.
Otherwise the **Model** is left to speak for itself. `language_auto_detected`
means exactly "this **Model** may be asked to synthesize without a **Language**":
no **Language** then reaches the **TTS Engine**, and nothing is detected on the
server's behalf. A **Model** that declares several **Languages** and no
`language_auto_detected` has neither a **Language** to fill in nor one to invent,
so a request reaching it without one is an error naming the **Model** and every
declared **Language**.
_Avoid_: locale, locale string

**Text Format**:
The input format a **TTS Engine** accepts for a **Model** during synthesis —
either `text` or `ssml`. Not every **Model** supports every format; a **Model**'s
support for `ssml` is declared via its `ssml_supported` flag.
_Avoid_: format, text type

**Speaker**:
The engine-level voice profile within a **Model** that the owning **TTS Engine**
selects during synthesis (e.g., a Silero speaker like `aidar`, or an OpenAI
voice name like `alloy`). Speakers are model-specific — the same speaker name
may refer to different profiles across different models.
_Avoid_: Voice (when meaning a speaker profile)

**Voice**:
A user-facing preset that references exactly one **Model** and the
engine-specific parameters needed to synthesize its speech — a **Speaker**
within that **Model**, or reference audio/text for cloning-style engines.
Multiple **Voices** can map to the same **Speaker** within a **Model**.
_Avoid_: Speaker (when meaning a named voice)

**Sentence**:
A segment of text split from the input by the **TTS Engine Hub** to stay within
model length limits. Multiple Sentences are synthesized separately and streamed
as a single audio response.
_Avoid_: Segment, fragment

**Chunk**:
Raw PCM audio produced by the **TTS Engine** for streaming over the
Wyoming protocol. Its samples are C-contiguous, so the Wyoming handler can turn a
Chunk into bytes without copying it. Yielding a Chunk hands over the buffer behind it:
the **TTS Engine Hub** draws **Frames** from that buffer, so a **TTS Engine** must not
recycle or mutate the audio it has yielded until the Hub has yielded the last Frame
drawn from it.
_Avoid_: Audio packet, byte fragment, PCM segment

**Frame**:
A bounded slice of one **Chunk** in samples, sized by the configured frame duration.
Frames are views over their **Chunk**'s audio, not copies of it, so that audio stays open
for reading until the last Frame drawn from it has been written. See **Chunk** for who
may not write to it in the meantime.
_Avoid_: Packet, block, window

**Text normalization**:
The preprocessing step applied by the **TTS Engine Hub** to text before TTS
synthesis that ensures clean input by stripping whitespace and removing
characters unavailable in the active model.
_Avoid_: Preprocessing, text cleaning, normalization (alone)

**VoiceNormalization**:
A per-voice, per-**Text Format**, per-**Language** override of normalization
settings. Links a voice to a specific normalization type (simple or openai) for
a bare **Language** code, optionally referencing a reusable prompt. When
present, it overrides the server-wide default for that voice, **Text Format**,
and **Language** combination.
_Avoid_: Normalization override, voice normalisation config

**Prompt**:
A reusable LLM prompt definition that specifies the instruction text and which LLM model to use for LLM-based text normalization.
_Avoid_: LLM instruction

**Active Model**:
A **Model** that the running instance actually serves — enabled **and** listed in the instance's `active_models` allowlist. Only **Active Models**' **Voices** are advertised over the **Wyoming** protocol.
_Avoid_: loaded model, warmed-up model

## Relationships

- A **TTS Engine Hub** aggregates one or more **TTS Engines**
- A **TTS Engine** owns one or more **Models**
- A **Model** belongs to exactly one **TTS Engine**
- A **Model** supports one or more **Speakers** and one or more **Languages**
- A **Model** declaring `language_auto_detected` may be asked to synthesize a
  request that carries no **Language**; one declaring several **Languages** and
  no `language_auto_detected` cannot be served a request that carries none
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

## Example dialogue

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
> **Dev:** "How does the Hub handle a **Language** from a Wyoming client?"
> **Domain expert:** "It's optional. If the client sends one, the **TTS Engine
> Hub** validates it against the selected **Model**'s declared **Languages** and
> rejects the request on a mismatch. If the client omits one, the Hub fills it in
> from the **Model**'s sole declared **Language**, but only when the **Model**
> declares exactly one and doesn't auto-detect. Otherwise the **Model** decides:
> one declaring `language_auto_detected` may be asked to synthesize without a
> **Language**, and one declaring several **Languages** has no **Language** to
> guess, so the request is refused with an error naming them."
> **Dev:** "Does every model support SSML?"
> **Domain expert:** "No — the **Model** supports SSML if `ssml_supported` flag
> is set for **Model**; some engines only accept plain text."

## Flagged ambiguities

- "Model" was used to mean both a config entry and the loaded neural network —
  resolved: **Model** is a configuration concept
- "TTS model" was used to mean both a provider family (Silero, Qwen3-tts, an
  OpenAI-compatible API) and a specific named model — resolved: a provider
  family is a **TTS Engine**; a specific named model is a **Model**
- "Active" was used overlapping with the `enabled` flag — resolved:
  `active_models` is a runtime allowlist filter layered on top of `enabled`; a
  model must be both to be served