# `dev` channel

This is the active control-cluster channel overlay for INIT-009.

The channel id is `dev`, matching `infra/channels/dev.yaml`.

This overlay composes the Flux base, the scheduled downstream control-plane
bases, and the `secrets/dev` per-channel secrets root.

The downstream bases are intentionally empty until INIT-017, INIT-018, and
INIT-019 populate them.
