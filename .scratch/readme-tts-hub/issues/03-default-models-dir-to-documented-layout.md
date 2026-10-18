---
title: "Default the models directory to the layout the docs and image use"
labels:
  - ready-for-agent
created: 2026-10-18
---

Status: done

## What to build

An operator who installs the server and sets nothing gets a models directory
that neither the README nor the Docker run command describes, so downloaded
models land where nothing is looking for them.

The built-in default for the models directory disagrees with the value the
shipped configuration sets and with the volume the documented Docker command
mounts. Because the shipped configuration sets it explicitly, this only bites a
reader who removes that line, runs from a different working directory, or copies
the settings into their own environment — but it fails quietly, as an engine
that re-downloads on every start.

Make the built-in default the same directory the shipped configuration and the
documented container layout use.

## Acceptance criteria

- [x] The built-in default models directory is the same directory the shipped
      configuration uses
- [x] That directory is the one the documented Docker run command mounts
- [x] An engine downloads and caches its models where the documented layout says
      they live, with nothing overridden in configuration
- [x] Tests assert the default rather than the shipped file's value, so the two
      cannot drift apart silently

## Blocked by

None (can start immediately).
## Answer

`models_dir` is the **parent** of whatever layout a TTS Engine keeps its models in —
Silero stores its registry and weights under `silero/` inside it. The default named
`silero` as well, so it resolved to `models/silero/silero/…`, found nothing, and
re-downloaded on every start. The default is now `models`, matching both the shipped
configuration and the documented mount.

The failure was silent by construction, so each of the four criteria is pinned by a
test that fails against the old value:

- The Python default is asserted as a literal rather than read from `config.yml`, and
  a separate test asserts the shipped file agrees with it — so neither can drift alone.
- The documented mount is checked on both sides (the host's `./models` against the
  image's `WORKDIR /app`), and the image is checked to declare no volume of its own,
  which is what makes the run command's mount the only thing keeping a cache.
- A stored model is resolved, an uncached one is downloaded to the same place, and the
  Engine Factory is checked to hand the TTS Engine that directory — the test resolves
  against the default directly, so without the factory check it would still pass if the
  wiring passed something else.

A review pass caught that the first version of the third test only proved *resolution*:
it pre-placed the `.pt` file, so it took the cache-hit branch and never reached the
download. That is now covered too.
