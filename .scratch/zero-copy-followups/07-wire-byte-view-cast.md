---
title: "Build the wire byte view with a cast, not a dtype view"
labels:
  - ready-for-agent
created: 2026-10-15
---

## What to build

The Wyoming handler hands the socket a byte view that is correct for any audio a TTS
Engine can produce, and allocates one object per frame instead of two.

The announced payload length and the bytes actually written currently agree because the
handler reinterprets the frame's buffer as a different dtype, whose element size happens
to be one byte. That is incidental: a Frame held as a plain memory view reports its
length in samples rather than in bytes, and Wyoming announces that length in the event
header before writing the payload. A Frame must therefore be a byte view, and it should be
one because it is a byte view, not because of what one dtype reinterpretation happens to
produce.

The cast form also survives a degenerate audio array that has no sample axis, which the
dtype view refuses.

## Acceptance criteria

- [ ] The announced payload length always equals the bytes written, for any audio a TTS
      Engine can yield
- [ ] The handler builds one memoryview per frame rather than a buffer view plus a memoryview
- [ ] The audio still reaches the socket as a view; Frames continue to share their Chunk's buffer
- [ ] Static analysis reports the same single known annotation mismatch at that site, with the
      same explanatory note
- [ ] The full test suite passes and no other static-analysis finding changes

## Blocked by

- None (can start immediately)
