# INIT-111 Risk Gate: Audit

Verdict: LOW

The proposal is auditable because it records the CNPG release, Atlas chart
version, namespaces, sample cluster name, Infisical project/path, migration
directory, and backup target in source-controlled contracts. Raw rendered
operator manifests are committed, and the validation harness checks the applied
runtime state instead of relying only on render success.

Residual observation: CNPG and Atlas rendered manifests are large. That is
acceptable for this substrate slice because the render inputs and versions are
committed beside the output.
