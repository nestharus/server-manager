# `crossplane` (placeholder)

This base is reserved for **INIT-017: Crossplane Control Plane** to populate.

Until INIT-017 ships, the `kustomization.yaml` is intentionally empty (`resources: []`).

The `gitops/channels/dev/kustomization.yaml` composes this empty base so that:
- The composition contract is established now
- INIT-017 can populate without changing channel composition
- The harness can detect drift if any resource is added before INIT-017 owns the base

When INIT-017 ships, replace this README with content describing the actual base composition.
