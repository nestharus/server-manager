# `cert-manager` (placeholder)

This base is reserved for **INIT-018: Cluster DNS and Certificates** to populate.

Until INIT-018 ships, the `kustomization.yaml` is intentionally empty (`resources: []`).

The `gitops/channels/dev/kustomization.yaml` composes this empty base so that:
- The composition contract is established now
- INIT-018 can populate without changing channel composition
- The harness can detect drift if any resource is added before INIT-018 owns the base

When INIT-018 ships, replace this README with content describing the actual base composition.
