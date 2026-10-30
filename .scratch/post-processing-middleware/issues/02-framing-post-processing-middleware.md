---
title: "Framing moves into a post-processing middleware"
labels:
  - ready-for-agent
created: 2026-10-30
---

# 02: Framing moves into a post-processing middleware

**What to build:** A client still receives Frames sized to the configured frame
duration, but framing is now the final audio post-processing step in the
middleware chain rather than a responsibility of the TTS Engine Hub. The Hub no
longer knows the frame duration or how to frame, and every default wiring —
server, benchmark, and tests — includes the framing middleware. A Hub wired
without it emits raw Chunks. The domain glossary records Audio Post-processing
and the updated relationship between Chunks and Frames.

**Blocked by:** 01-onion-middleware-chain.md

**Status:** ready-for-agent

- [x] Each Chunk is split into Frames of the configured duration, with a shorter
      trailing Frame when the Chunk does not fill a whole one
- [x] Frames remain views over the Chunk's audio, copying nothing
- [x] The TTS Engine Hub no longer accepts a frame duration, and a Hub without
      the framing middleware yields raw Chunks
- [x] Default server, benchmark, and test wiring include the framing middleware
      and clients still receive Frames
- [x] Framing runs after any inner audio post-processing, so inner middleware
      see Chunks and outer middleware see Frames
- [x] `GLOSSARY.md` defines Audio Post-processing and updates the Frame
      relationship accordingly
