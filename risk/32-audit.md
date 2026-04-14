# Risk Assessment: Audit — K8s GitOps Manifests

## Verdict: LOW

## Findings

1. **LOW — Pinned chart versions prevent supply chain drift.**
   Both HelmReleases pin exact chart versions (`kube-prometheus-stack`
   `83.4.1`, `sealed-secrets` `2.18.5`). No version ranges, floating
   tags, or `>=` constraints are used. This eliminates the most common
   Helm supply chain vector: silent upstream upgrades introducing
   unexpected behavior.

2. **LOW — No external service exposure.**
   Grafana ingress is explicitly disabled (`grafana.ingress.enabled:
   false`). Sealed-secrets ingress is disabled. Alertmanager has no
   ingress configuration. All services remain cluster-internal in
   Phase 1, eliminating unauthenticated external access vectors.

3. **LOW — Sealed-secrets runs non-root with read-only root filesystem.**
   The proposal relies on the chart's default security context
   (`runAsNonRoot`, read-only root filesystem, `fsGroup: 65534`).
   These defaults are confirmed in the research document from the
   upstream `values.yaml`. No overrides weaken the posture.

4. **LOW — Explicit resource limits on all components.**
   Every component — Prometheus, Alertmanager, Grafana,
   kube-state-metrics, node-exporter, Prometheus Operator, config
   reloader, and sealed-secrets — has explicit CPU and memory requests
   and limits in both base and staging. This prevents unbounded
   resource consumption on the 1-3 node k3s cluster and mitigates
   noisy-neighbor denial-of-service within the cluster.

5. **LOW — No secret material committed to the repository.**
   The proposal adds only manifest structure (Kustomization files,
   HelmReleases, overlay patches). No actual secrets, tokens, keys,
   credentials, or SealedSecret objects are introduced. Flux bootstrap
   credentials are managed separately by the bootstrap process.

6. **MEDIUM — No network policies defined.**
   Neither the monitoring nor secrets namespace defines
   `NetworkPolicy` objects. All pods can communicate freely within
   the cluster. On a small, tightly-controlled k3s cluster this is
   acceptable for Phase 1 bootstrap, but it means a compromised pod
   could reach the sealed-secrets controller or Prometheus API without
   restriction. The sealed-secrets chart has `networkPolicy` disabled
   by default and the proposal does not override this.

7. **MEDIUM — Permissive ServiceMonitor/PodMonitor selectors.**
   The proposal sets `serviceMonitorSelector: {}`,
   `podMonitorSelector: {}`, and `probeSelector: {}` with the
   corresponding `*NilUsesHelmValues: false` flags. This means
   Prometheus will scrape any ServiceMonitor, PodMonitor, or Probe
   in any namespace. On a small cluster with controlled workloads
   this is a reasonable extensibility choice, but it widens the
   scrape surface — a malicious or misconfigured ServiceMonitor could
   cause Prometheus to scrape unintended endpoints or consume
   excessive resources via cardinality explosion.

8. **MEDIUM — Container images referenced by tag, not digest.**
   The HelmReleases pin chart versions but do not pin container image
   digests (e.g., `image.tag` or `image.digest` overrides in
   `spec.values`). The chart defaults pull images by tag. A
   compromised registry could serve a different image for the same
   tag. This is standard practice for Phase 1 bootstraps and the risk
   is mitigated by using official community registries, but it is not
   zero.

9. **MEDIUM — Sealed-secrets key backup/restore is explicitly deferred.**
   The proposal's anti-scope section states that key backup/restore
   automation is out of scope. The research confirms that sealing keys
   auto-renew every 30 days and backups must be refreshed after each
   renewal. During the window before backup procedures are
   established, a controller or node loss could render all existing
   SealedSecret objects permanently unrecoverable. This is an
   operational risk, not a code risk, but it has data-integrity
   implications.

10. **LOW — No Helm chart signature verification.**
    Neither HelmRepository object configures chart signature
    verification (e.g., cosign/sigstore). This is consistent with
    the current Flux ecosystem where chart verification is not yet
    widely adopted, and the risk is partially mitigated by pinned
    versions from official repositories.

11. **LOW — Ephemeral storage is a deliberate, documented tradeoff.**
    Prometheus uses `emptyDir: {}`, Alertmanager uses `storage: {}`,
    and Grafana persistence is disabled. Metrics history, alert
    silences, and Grafana state are lost on pod reschedule. The
    proposal documents this as an explicit Phase 1 decision with
    durable PVC-backed storage as follow-on work. No silent data
    loss — the tradeoff is visible and intentional.

12. **LOW — No GDPR or personal data concerns.**
    The monitoring stack collects cluster infrastructure metrics
    (CPU, memory, pod status), not user-facing application data or
    PII. Grafana is internal-only with no user-facing dashboards.
    Sealed-secrets handles encryption keys, not personal data.

## Justification

The proposal carries **LOW** overall audit risk. It is a
manifest-layer-only change that adds declarative Kubernetes YAML with
no executable logic, no secret material, and no external exposure.

The conservative security posture — disabled ingress on all services,
pinned chart versions, explicit resource limits on every component,
reliance on upstream non-root security contexts, and ephemeral storage
as a documented deliberate choice — minimizes the attack surface.

The three MEDIUM findings (no network policies, permissive monitor
selectors, deferred key backup) are reasonable Phase 1 tradeoffs for
a small, tightly-controlled k3s cluster:

- **Network policies** are typically layered in after baseline
  services are running and traffic patterns are understood. Adding
  them in Phase 1 bootstrap before workloads exist would be premature
  and would risk blocking legitimate controller-to-API-server traffic.
- **Permissive selectors** are explicitly chosen for extensibility
  and are acceptable when the cluster operator controls all deployed
  ServiceMonitors.
- **Key backup deferral** creates an operational gap but does not
  introduce a code-level vulnerability; it is documented in
  anti-scope and acknowledged in the research.

None of the findings represent immediately exploitable vulnerabilities.
The image-tag-vs-digest gap and absent chart signature verification
are industry-standard practices at this maturity phase and are
mitigated by version pinning and use of official upstream repositories.
