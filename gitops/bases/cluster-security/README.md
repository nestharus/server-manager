# `cluster-security` (placeholder)

This base is reserved for **INIT-019: Cluster Security Baseline** to populate.

Until INIT-019 ships, the `kustomization.yaml` is intentionally empty (`resources: []`).

The `gitops/channels/dev/kustomization.yaml` composes this empty base so that:
- The composition contract is established now
- INIT-019 can populate without changing channel composition
- The harness can detect drift if any resource is added before INIT-019 owns the base

When INIT-019 ships, replace this README with content describing the actual base composition.
