---
title: "Decide whether Text Formats are advertised over Wyoming"
labels:
  - ready-for-human
created: 2026-10-17
---

## What to build

The glossary says the server advertises, per **Model Info**, its **Languages**
and its **Text Formats**. The advertised payload carries Voices and Languages
only — a **Text Format** is resolved per request and never announced.

Decide which side is wrong, then act on it:

- **The model is right** — the server should announce each **Model Info**'s
  **Text Formats** alongside its **Languages**, so a client can discover SSML
  support before sending it. Requires a protocol payload change and a client
  compatibility check.
- **The glossary is wrong** — a **Text Format** is a per-request choice, not an
  advertised capability. Amend the glossary relationship and leave the code alone.

Note that `ssml_supported` is parsed onto a **Model Info** but never read at
synthesis time, so under either option it is currently decoration. If the first
option is chosen, resolve that too.

## Acceptance criteria

- [x] A decision is recorded, and the glossary and the advertised payload agree
- [x] `ssml_supported` is either read or removed — it does not stay inert
- [x] Client compatibility is considered before the payload changes

## Answer

**The glossary was wrong.** The upstream `wyoming` protocol's advertised voice
carries a name, a description, attribution, `installed`, `version`, `languages`
and `speakers`. There is no field for **Text Formats**, so announcing them would
mean changing an upstream library's payload — and clients ignore unknown fields
anyway, so a client could not rely on one. A **Text Format** is therefore a
per-request choice, and the glossary relationship now says so.

That settles the payload half of the question, but not the flag. The upstream
payload being unchanged is *not* the same as no client regressing, and the
acceptance criteria separate the two.

**`ssml_supported` is now read** rather than removed. It becomes a declaration the
TTS Engine Hub enforces, alongside the existing **Language** check: a request
carrying SSML for a **Model Info** whose `ssml_supported` is false is refused,
naming both the Text Format and the Model Info. Plain text needs no declaration
and is always accepted.

This is a behaviour change, and the compatibility consequence is real:
`ssml_supported` defaults to false, so a **Model Info** that omits the flag now
refuses SSML where it previously spoke it — the Silero engine has an SSML
synthesis path regardless of what the data file declares. Both models shipped in
the data file declare `ssml_supported: true`, so the shipped configuration does
not regress; a configuration that omits the flag and relies on SSML must add it.
The alternative under the ticket's second branch was to delete the flag, but
SSML support is real, the domain already distinguishes plain text from SSML in
normalization and sentence splitting, and deleting the declaration would have
left SSML accepted by every **Model Info** whether it can speak it or not.

Documenting `ssml_supported` for anyone configuring a **Model Info** is folded
into `.scratch/docs-readme-refactor/01-align-readme-with-model-and-voice.md`,
which is already rewriting the model keys.

## Blocked by

None - can start immediately