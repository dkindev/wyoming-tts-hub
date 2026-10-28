---
title: "Serve the real-model stream check under the local Model Info id"
labels:
  - ready-for-agent
created: 2026-10-28
---

## What to build

Make the real-model stream check activate the shipped local Model Info id instead
of its upstream id, while still resolving the Silero registry entry and cached
checkpoint by the upstream id.

The check should pass `silero_ru` in `active_models`, keep `v5_6_ru` for the
registry lookup and cache path, and assert the loaded Model Info keeps the local
`id` and upstream `id` it was configured with. It must not depend on a local `.env`
file to select the model.

## Acceptance criteria

- [ ] The real-model stream check activates the local Model Info id
- [ ] The registry lookup and cached checkpoint path still use the upstream id
- [ ] The check asserts the Model Info's local id and upstream id
- [ ] The check passes without relying on a local `.env` file

## Blocked by

None (can start immediately).
