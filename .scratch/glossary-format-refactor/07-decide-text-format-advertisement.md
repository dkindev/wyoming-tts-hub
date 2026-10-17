---
title: "Decide whether Text Formats are advertised over Wyoming"
labels:
  - ready-for-agent
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

- [ ] A decision is recorded, and the glossary and the advertised payload agree
- [ ] `ssml_supported` is either read or removed — it does not stay inert
- [ ] Client compatibility is considered before the payload changes

## Blocked by

None - can start immediately