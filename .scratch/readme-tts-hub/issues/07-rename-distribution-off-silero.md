---
title: "Rename the distribution and repository off Silero"
labels:
  - ready-for-agent
created: 2026-10-18
---

## What to build

The project is a TTS Engine Hub that aggregates engines, but its distribution,
repository and command are all named after the first engine it shipped with. A
reader cloning `silero-server` expects Silero, and finds a hub.

Rename them together, so the package name, the repository, the command and the
documentation all say the same thing.

One stray file survives the rename and needs a decision rather than a
mechanical edit: a standalone sample script that hardcodes a CUDA device, is
imported by nothing, and is not part of the server's path. Either bring it under
the new naming and make it runnable, or delete it.

## Acceptance criteria

- [ ] The distribution is named for the hub, not for one engine family
- [ ] The console script, the repository URL and the documented clone URL all
      carry the new name
- [ ] The installed package's metadata reads under its new name, and the server
      still starts
- [ ] A test asserts the metadata lookup resolves, since the name the package
      asks for is part of its own identity
- [ ] The stray sample script is either renamed and made runnable, or removed —
      with the decision recorded in the pull request
- [ ] The README carries the new clone URL and image tag

## Blocked by

- 04: Run the server from an installed console script
- 05: Describe the package as the TTS Engine Hub it is