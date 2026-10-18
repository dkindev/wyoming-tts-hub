---
title: "Default the models directory to the layout the docs and image use"
labels:
  - ready-for-agent
created: 2026-10-18
---

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

- [ ] The built-in default models directory is the same directory the shipped
      configuration uses
- [ ] That directory is the one the documented Docker run command mounts
- [ ] An engine downloads and caches its models where the documented layout says
      they live, with nothing overridden in configuration
- [ ] Tests assert the default rather than the shipped file's value, so the two
      cannot drift apart silently

## Blocked by

None (can start immediately).