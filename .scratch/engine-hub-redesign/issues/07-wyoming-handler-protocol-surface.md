---
title: "The Wyoming handler answers Describe and Synthesize"
labels:
  - ready-for-agent
created: 2026-10-05
---

Status: done

## What to build

The Wyoming event handler is how Wyoming clients — Home Assistant among them —
discover the server's Voices and request speech. After the redesign it drives the
TTS Engine Hub rather than a synthesis engine directly, and it has no tests. This
is the outermost layer, and nothing below it is verifiable from a client's point
of view without it.

Deliver coverage of the protocol surface:

**Describe.** A Describe request is answered with a single program advertising
the service. Its Voice list contains only the Active Models' Voices, sorted by
name, each carrying the Languages declared by its Model.

**Synthesize.** A Synthesize request produces an audio-start event, one or more
audio-chunk events, then an audio-stop event. The start event is sent exactly
once no matter how many chunks follow, and reports the same rate, width, and
channel count as the chunks.

**Rejections.** Each of these produces an error event and no audio, rather than
an exception escaping to the client: empty or whitespace-only text; a request
with no Voice; an unknown Voice; a Text Format the server does not accept.

**Error detail.** When the server runs in production mode, a failure inside
synthesis is reported to the client as a generic internal error rather than
leaking internals. In development mode the underlying message is included.

**Streaming.** With streaming enabled, a start/chunk/stop sequence streams
audio from the chunks as they arrive and confirms the stop. With streaming
disabled, those events are ignored and only a whole-request Synthesize is served.

## Acceptance criteria

- [x] A Describe request is answered with one program whose Voice list matches
      the Active Models' Voices, sorted by name
- [x] Each advertised Voice reports the Languages declared by its Model
- [x] A Synthesize request emits audio-start, then audio chunks, then audio-stop
- [x] Audio-start is emitted exactly once regardless of chunk count
- [x] Every emitted event agrees on rate, width, and channel count
- [x] Empty text, a missing Voice, an unknown Voice, and an unparseable Text
      Format each produce an error event and no audio
- [x] In production mode a synthesis failure reports a generic internal error;
      in development mode it includes the underlying message
- [x] With streaming disabled, the streaming events are ignored
- [x] Tests drive the handler through its event interface, asserting on the bytes
      written to the client

## Blocked by

- [03: Engine Hub routes a Voice to its Model and frames the audio](03-engine-hub-routing-and-framing.md)