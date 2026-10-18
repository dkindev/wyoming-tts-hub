---
title: "Rename the distribution and repository off Silero"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

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

- [x] The distribution is named for the hub, not for one engine family
- [x] The console script, the repository URL and the documented clone URL all
      carry the new name
- [x] The installed package's metadata reads under its new name, and the server
      still starts
- [x] A test asserts the metadata lookup resolves, since the name the package
      asks for is part of its own identity
- [x] The stray sample script is either renamed and made runnable, or removed —
      with the decision recorded in the pull request
- [x] The README carries the new clone URL and image tag

## Blocked by

- 04: Run the server from an installed console script
- 05: Describe the package as the TTS Engine Hub it is
## Answer

The distribution, the command, the Docker tag and the documented clone URL are all
`wyoming-tts-hub` now, along with the `importlib.metadata` lookup the package makes about
itself and its own entry in `uv.lock`.

**The stray sample script was deleted, not renamed.** It hardcoded a CUDA device, was
imported by nothing, downloaded a model at import, and was never tracked in git — so no
reviewer would ever have seen it, while it did break `ruff check src tests` for anyone
whose working directory happened to contain it. Nothing in the server's path used it.
With it gone, `ruff check src tests` passes over the whole tree with no exclusions,
which it could not before.

Two build artefacts were removed alongside it, for the same reason: a stale `build/`
directory and two `silero_server.egg-info` directories, all gitignored, all still
carrying the old name and the old command, and all being picked up by a wheel build. A
wheel built from that tree shipped the deleted script. The wheel now builds clean, with
no occurrence of the old name in any of its sources.

**The GitHub repository has not been renamed.** The URLs in `pyproject.toml` and the
README's clone line now point at `dkindev/wyoming-tts-hub`, which does not exist yet —
`git remote -v` still reads `silero-server`, and renaming the repository is out of band
from the code. Those links 404 until it happens. The Homepage URL is not only a link:
it is what a client is given as the server's attribution, so the rename is worth making
on GitHub before this ships rather than after.

**Two names, deliberately.** The distribution and the command are `wyoming-tts-hub`; the
project calls itself `Wyoming TTS Hub`, with a space, in `PROJECT_NAME` and in `app_name`.
That is the difference between a name typed on a command line and one displayed to a
person, and a test pins them apart. A hyphenated project name would have been tidier, but
it is not worth conflating the two.
