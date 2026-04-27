# INIT-116 Shortcut Risk

Risk: LOW.

No compatibility shim or fallback path was added. The tenant namespace and
Infisical project names are deterministic, tests assert the exact model, and
the live proof checks the actual Kubernetes/Cedar decisions rather than only
rendered YAML.
