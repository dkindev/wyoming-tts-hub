# Wyoming TTS Hub — Domain Context

The domain of a Wyoming-protocol text-to-speech server: a **TTS Engine Hub**
aggregating **TTS Engines**, each owning **Model Infos** and the **Voices** built
on them. This context exists so one vocabulary describes configuration, the
synthesis pipeline, and the audio streamed to clients.

## Language

### Engines and models

**TTS Engine Hub**:
The top-level component that aggregates **TTS Engines** and routes each synthesis
request to the **TTS Engine** that owns the requested **Model Info**.
_Avoid_: TTS server, orchestrator

**TTS Engine**:
A backend that synthesizes speech from text for one provider family (e.g. Silero,
Qwen3-tts, an OpenAI-compatible API), producing raw PCM audio.
_Avoid_: Speech generator, voice synthesizer

**Model Info**:
A named, language-specific model belonging to exactly one **TTS Engine**,
declaring its `engine_type`, the **Languages** it supports, whether it may be
asked to synthesize without one (`language_auto_detected`), and whether it accepts
SSML (`ssml_supported`).
_Avoid_: Neural network, PyTorch model

**Active Model Info**:
A **Model Info** that the running instance serves — enabled (`enabled`) **and**
named in the instance's `active_models` allowlist.
_Avoid_: loaded model, warmed-up model

### Voices

**Speaker**:
The engine-level voice profile within a **Model Info** that the owning **TTS
Engine** selects during synthesis (e.g. a Silero speaker like `aidar`, or an
OpenAI voice name like `alloy`). Speakers are model-specific — the same speaker
name may refer to different profiles across different models.
_Avoid_: Voice (when meaning a speaker profile)

**Voice**:
A named, user-facing preset that references exactly one **Model Info** and the
engine-specific parameters for speaking in it — a **Speaker** within that **Model
Info**, or reference audio and text for cloning-style engines. Multiple **Voices**
can map to the same **Speaker** within a **Model Info**.
_Avoid_: Speaker (when meaning a named voice)

**VoiceNormalization**:
A per-**Voice**, per-**Text Format**, per-**Language** override of normalization
settings, linking a **Voice** to a normalization type and optionally to a reusable
**Prompt**.
_Avoid_: Normalization override, voice normalisation config

**Prompt**:
A reusable LLM prompt definition that specifies the instruction text and which
LLM model to use for LLM-based **Text Normalization**.
_Avoid_: LLM instruction

### Language and text

**Language**:
A spoken-language code (e.g. `ru`, `en`) that a **Model Info** declares it
supports. A Wyoming client may send one; `language_auto_detected` means exactly
"this **Model Info** may be asked to synthesize without a **Language**", and
nothing is detected on the server's behalf.
_Avoid_: locale, locale string

**Text Format**:
The input format a **TTS Engine** accepts for a **Model Info** during synthesis —
either `text` or `ssml`.
_Avoid_: format, text type

**Text Normalization**:
The preprocessing step applied by the **TTS Engine Hub** to text before
synthesis.
_Avoid_: Preprocessing, text cleaning, normalization (alone)

### Synthesis pipeline

**Sentence**:
A segment of text split from the input by the **TTS Engine Hub**. Multiple
Sentences are synthesized separately and streamed as a single audio response.
_Avoid_: Segment, fragment

### Audio

**Chunk**:
Raw PCM audio produced by a **TTS Engine** for streaming over the Wyoming
protocol.
_Avoid_: Audio packet, byte fragment, PCM segment

**Frame**:
A bounded slice of one **Chunk**, in samples.
_Avoid_: Packet, block, window

## Relationships

- A **TTS Engine Hub** aggregates one or more **TTS Engines**, and coordinates
  warmup and shutdown across them
- A **TTS Engine** owns one or more **Model Infos**; a **Model Info** belongs to
  exactly one **TTS Engine**
- A **Model Info** supports one or more **Speakers** and one or more **Languages**
- A **Speaker** belongs to exactly one **Model Info**, and within that **Model
  Info** may be referenced by one or more **Voices**
- A **Voice** references exactly one **Model Info** and either exactly one
  **Speaker** or engine-specific reference parameters; the language of its speech
  is derived from the **Model Info**
- A **Voice** has zero or more **VoiceNormalizations**; a **Prompt** is referenced
  by zero or more **VoiceNormalizations**
- A **Model Info**'s declared **Languages** are the source of truth advertised
  for its **Voices**
- The **TTS Engine Hub** splits text into **Sentences** so each stays within the
  configured sentence length limit, applies **Text Normalization** to each
  **Sentence**, then routes them to the **TTS Engine** that owns the requested
  **Model Info**
- A **TTS Engine** synthesizes each **Sentence** into one or more **Chunks**,
  which the server streams over the Wyoming protocol
- A **Frame** is a slice of a **Chunk** sized by the configured frame duration
- A **Model Info** is loaded on the first synthesis request for it, unless it sets
  `warmup` to be pre-warmed at startup
- Only the **Voices** of **Active Model Infos** are advertised over the Wyoming
  protocol, plus their per-**Model Info** **Languages**
- A **Text Format** is chosen per request rather than advertised: the Wyoming
  protocol announces a **Voice**, its **Languages** and its speakers, and says
  nothing about **Text Formats**
- A **Model Info** that does not declare SSML support (`ssml_supported`) refuses
  an SSML request; plain text is always accepted
- A **Language** sent by a client is validated against the selected **Model
  Info**'s declared **Languages**, and the request is refused on a mismatch
- An omitted **Language** is filled in from the **Model Info**'s sole declared
  **Language**, but only when that **Model Info** declares exactly one and does
  not auto-detect
- A **Model Info** declaring several **Languages** and no
  `language_auto_detected` has neither a **Language** to fill in nor one to
  invent, so a request reaching it without one is refused with an error naming
  the **Model Info** and every declared **Language**
- A **VoiceNormalization** overrides the server-wide normalization default for
  its **Voice**, **Text Format** and **Language** combination