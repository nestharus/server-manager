# INIT-108 Risk Gate: Shortcut

Result: LOW

- The local proof is real build, push, pull, and run rather than a static-only substitute.
- Registry credentials use InfisicalSecret instead of SOPS.
- Pull-through cache is configured in k3d/containerd, not documented as a manual workaround.
