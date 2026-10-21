---
title: "Make the Qwen3-TTS runtime available"
labels:
  - completed
created: 2026-10-19
---

## What to build

The Qwen3-TTS TTS Engine cannot be written until the upstream Qwen3-TTS runtime
is importable alongside this project's CPU-pinned torch.

Add it as a runtime dependency, pin its audio companion to the same torch build
and index so the resolver cannot install a second torch, and make the container
image able to import it. Verify the upstream package's pinned Transformers
release actually works with this project's torch before declaring the ticket
done; if it does not, stop and report rather than pinning around it.

Record next to the dependency why the install closure is so large. The upstream
package imports its 25 Hz speech tokenizer eagerly at package import, which
pulls in audio and inference libraries that the 12 Hz path never uses, and it
declares a web UI that is only reachable through its own demo command.

## Acceptance criteria

- [x] Qwen3-TTS is a runtime dependency, and its audio companion is pinned to the same package index as torch (torchaudio 2.11.0, its final release; no 2.12 build exists)
- [x] A clean sync installs exactly one torch build
- [x] Importing the upstream package succeeds in the development environment
- [x] The container image installs whatever system library the audio dependency needs and imports the upstream package
- [x] A comment records why the extra audio/inference/UI dependencies are in the closure
- [x] The existing test suite and lint stay green

## Implementation notes

- `torchaudio` has no 2.12 release, so it stays on its final `2.11.0` build from the
  same `pytorch-cpu` index. Its `fbank` and `resample` operations were verified against
  `torch==2.12.1+cpu`.
- `transformers==4.57.3` was verified on `torch==2.12.1+cpu` with a model forward pass.

## Blocked by

None — can start immediately
