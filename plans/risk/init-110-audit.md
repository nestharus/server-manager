# INIT-110 Risk Gate: Audit

Verdict: LOW

The proposal is auditable because it records the upstream chart name, chart
version, rendered values, installed images, ingress class, issuer names, host
patterns, and sample proof path in source-controlled artifacts. The Kong chart
render is committed as raw YAML, so reviewers can inspect the actual Kubernetes
objects that Flux applies.

Residual observation: a future chart update will produce a large diff. That is
acceptable for this substrate slice because the values file and chart version
make the change reproducible.
