# INIT-115 Audit Risk

Risk: LOW.

The change is additive to GitOps policy contracts and scripts. Runtime mutation
paths are opt-in and guarded. The local root removes only the broad
`crossplane-admin` binding while preserving Crossplane controller bindings.
