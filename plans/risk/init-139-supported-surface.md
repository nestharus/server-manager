# INIT-139 — Supported-surface risk gate

**Verdict:** LOW

INIT-139 (`proposals/34-init-139-kong-kic-smoke.md`) adds one new
read-only shell validator
(`infra/tests/validate_kong_kic_translation_local.sh`), wires it as a
single command line into the existing
`pr-cluster-merge-readiness-runtime-validators` step in
`.buildkite/pipeline-cluster.yml`, and protects the validator + wiring
with two small pytest guards under `infra/tests/`. The slice is a
runtime-only smoke that introspects Kong's Admin API through a
temporary `kubectl port-forward` and asserts five public-intake Kong
Routes carry a route-scoped `rate-limiting` plugin while the adjacent
admin path catch-all does not. Proposal §5 ("Anti-scope") and §6
("Diff budget") explicitly forbid any change to public API contracts,
env vars, Alembic migrations, Pomerium config, Authentik blueprints,
OPAL/Cedar bundles, Kong/KIC manifests, BL-014 static pins, or any
Discord-visible mutation. No new Kubernetes Service, NodePort, or
LoadBalancer is created — Admin API access is loopback-only via
port-forward, matching the rendered chart's existing
`KONG_ADMIN_LISTEN=127.0.0.1:8444` posture.

## Surfaces touched

### 1. No public API change

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `services/api/app/api/v1/endpoints/...` route set | post-INIT-137 / post-SLICE-032 set (`/api/v1/public/applications`, `/api/v1/public/applications/upload-url`, `/api/v1/public/chapters`, plus authenticated routes) | unchanged — proposal §5 anti-scope explicitly excludes "Modifying Kong manifests, KIC manifests, Pomerium manifests, or server-manager Ingress manifests" and §6 diff budget excludes "application code, API contracts, migrations, generated TypeScript, web code, Discord daemon code, or Kubernetes manifest changes" | **none** |
| `PublicApplicationSubmission` / `PublicApplicationSubmissionReceipt` contracts | post-INIT-137 set (`services/api/app/contracts/applications.py`) | unchanged — INIT-139 ships no Pydantic field, no schema, no contract addition | **none** |
| Public chapters / public applications path prefixes (`/api/public/applications`, `/api/public/chapters`, `/api/applications`, `/api/v1/public/applications`, `/api/v1/public/chapters`) | post-INIT-137 set | unchanged — the validator *reads* these paths from live Kong Routes; it never asserts new paths or modifies the Ingress that produces them | **none** |
| Auth dependencies / receipt chain | post-INIT-137 set (`verify_applicant_receipt`, `authorize_public_intake`) | unchanged — Cedar policies are not touched; OPAL/Cedar bundle is anti-scope per proposal §5 (and the slice ships no policy material) | **none** |
| Web SPA submit flow (`services/web/`) | post-INIT-137 / post-SLICE-030 set | unchanged — proposal §6 explicitly excludes "web code" from the diff budget | **none** |
| Discord daemon | unchanged | unchanged — proposal §5 anti-scope: "Any Discord-visible mutation"; §6 excludes "Discord daemon code" | **none** |

Risk on §1: **none**. No FastAPI route, request model, response
model, dependency, error mapper, service module, contract, web
caller, or Discord daemon path is touched. The slice is a runtime
read-only Admin API smoke plus two static pytest guards.

### 2. Validator is operator-callable + idempotent

| Property | Pre | Post | Risk |
|---|---|---|---|
| Operator invocation | n/a (validator does not exist) | `infra/tests/validate_kong_kic_translation_local.sh --cluster` from the repo root, matching the existing `infra/tests/validate_*_local.sh --cluster` contract used by `validate_object_storage_local.sh`, `validate_tls_dns_local.sh`, `validate_app_clusters_local.sh`, `validate_cluster_security_local.sh`, and `validate_container_delivery_local.sh` | **none** — same shape an operator already uses on-call |
| Argument surface | n/a | `--cluster`, `--kubeconfig PATH`, `--help` per proposal §2 Q2; no required env vars beyond `KUBECONFIG_PATH` (default `${HOME}/.kube/humility-local.yaml`) which is identical to every other `validate_*_local.sh` validator | **none** |
| Idempotency | n/a | the validator is read-only over Kong's Admin API — `GET /routes` and `GET /routes/<route_id>/plugins` only (proposal §2 Q4 + §2 Q5). It performs zero `POST`/`PATCH`/`PUT`/`DELETE` calls, zero `kubectl apply`, zero `kubectl edit`, zero ConfigMap or Secret mutation, and zero KongPlugin/Ingress mutation. Re-running yields identical assertions against the same live state | **none** |
| Side-effect cleanup | n/a | proposal §2 Q3 mandates "the implementation must clean up the port-forward process in a `trap`". This matches the existing pattern in `validate_object_storage_local.sh` (port-forward log under `${REPO_ROOT}/.tmp/`, killed in cleanup) and `validate_observability_local.sh` (per-service port-forward with explicit teardown) | **none** |
| Output contract | n/a | `PASS:` / `FAIL:` / `ERROR:` lines per proposal §2 Q2 + §2 Q7, matching the existing `pass()` / `fail()` / `die()` helpers in `validate_kong_ingress_local.sh:55-78` and the rest of the local-validator family. Failure prints compact route id / hosts / paths / plugin names rather than full Admin API payloads (proposal §2 Q7) | **none** |
| Discord-visible writes | n/a | none — proposal §5 anti-scope: "Any Discord-visible mutation" | **none** |

Risk on §2: **none**. The validator is operator-callable in the
exact shape established by the existing `validate_*_local.sh` family,
is read-only over the Kong Admin API, and cleans up its only
side effect (the temporary port-forward process) in a `trap`. Re-runs
are safe by construction.

### 3. CI step is independently runnable from existing cluster lane

| Surface | Pre | Post | Risk |
|---|---|---|---|
| `.buildkite/pipeline.yml` (default lane) | post-INIT-137 / post-SLICE-031 / post-SLICE-032 set; runs `python -m pytest tests infra/tests`, service tests, web tests, static `--static-only` validators | unchanged — proposal §3 "Substrate / Modified file" lists only `.buildkite/pipeline-cluster.yml`; §3 explicitly says "Keep it in the cluster-runtime lane, not `.buildkite/pipeline.yml`." The pytest guards (TG-2, TG-3) ride along on the default lane's existing `pytest infra/tests` invocation; they require no new Buildkite step | **none** |
| `.buildkite/pipeline-cluster.yml` step `cluster-runtime-tooling-preflight` | pre-existing (`docker`, `k3d`, `kubectl` checks) | unchanged | **none** |
| `.buildkite/pipeline-cluster.yml` step `humility-local-cluster-bringup` | pre-existing (`infra/scripts/bring-up-local-channel.sh --channel local --force --cluster-only`) | unchanged | **none** |
| `.buildkite/pipeline-cluster.yml` step `pr-cluster-merge-readiness-runtime-validators` | pre-existing 5-line command block: `validate_object_storage_local.sh --cluster`, `validate_tls_dns_local.sh --cluster`, `validate_app_clusters_local.sh --cluster`, `validate_cluster_security_local.sh --cluster`, `validate_container_delivery_local.sh --cluster` | one new line appended: `infra/tests/validate_kong_kic_translation_local.sh --cluster`. Proposal §3 places it "after Kong, TLS/DNS, auth/server-manager, or existing readiness validators have made the live route state meaningful." Independent runnability is preserved because each line in the block is a standalone shell invocation that exits non-zero on failure under `set -e` semantics — Buildkite's command block is not a transaction | **none** |
| Operator can run the validator outside Buildkite | n/a | YES — proposal §4 TG-1 acceptance requires `infra/tests/validate_kong_kic_translation_local.sh --cluster` to run on a developer workstation against the existing `humility-local` k3d cluster. The validator does not depend on Buildkite environment variables, agent metadata, or pipeline-only fixtures. Same on-call ergonomic as the existing `validate_*_local.sh --cluster` scripts | **none** |
| 180-minute step timeout | pre-existing (`timeout_in_minutes: 180`) | unchanged — problem map §"Diff budget" projects the smoke "in well under 30 seconds after the cluster is already reconciled," well within the existing budget | **none** |

Risk on §3: **none**. The CI addition is a single command line in
the existing runtime-validator block. No new step, no new lane, no
new agent queue (`agents.queue: cicd-local` is preserved), no new
timeout, no new dependency edge. The validator is independently
runnable both from the cluster lane and from an operator's workstation
through the same `--cluster` flag the rest of the validator family
uses.

### 4. No env vars / migrations / Pomerium / Authentik / OPAL changes

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Process / `Settings` env vars (`services/api/app/core/settings.py`) | post-INIT-137 set | unchanged — proposal §6 diff budget: "No application code, API contracts, migrations, generated TypeScript, web code, Discord daemon code, or Kubernetes manifest changes are in budget" | **none** |
| `KUBECONFIG_PATH` validator default | pre-existing default `${HOME}/.kube/humility-local.yaml` across the `validate_*_local.sh` family | reused unchanged in the new validator (proposal §2 Q2). No new env var defined | **none** |
| Buildkite `env` block | pre-existing (`CHANNEL_ID: local`, `KUBECONFIG_PATH: "${HOME}/.kube/humility-local.yaml"`) | unchanged — proposal §3 "Modified file" wires the validator into the existing command block, not into the top-level `env` map | **none** |
| Alembic / DB migrations (`migrations/versions/`) | post-INIT-137 head | unchanged — proposal §6 explicitly excludes "migrations" from the diff budget; the slice ships no `services/api/` code | **none** |
| Pomerium routes / config / blueprint (`gitops/channels/local/auth/pomerium/**`, including `public-intake-rate-limit.yaml` and `secrets-infisicalsecret.yaml`) | post-INIT-137 set with `Ingress/web-public-intake` annotated `konghq.com/plugins: public-intake-rate-limit` for `web.local.humility.local` paths `/api/public/applications`, `/api/public/chapters`, `/api/applications` | unchanged — proposal §5 anti-scope: "Modifying Kong manifests, KIC manifests, Pomerium manifests, or server-manager Ingress manifests." The validator *reads* the runtime translation of these annotations from Kong's Admin API; it never edits the manifests that produced them | **none** |
| Authentik blueprint | post-INIT-134 set | unchanged — not touched by §3 substrate or §6 budget | **none** |
| OPAL / Cedar bundle (`policy/cedar/channels/local/services/server-manager-api/policies.json`) | post-BL-012 / post-INIT-135 set with `public-intake-allow` and `public-intake-no-read` for `Public::"web-intake.local"` | unchanged — proposal §6 budget enumerates only one new shell, one Buildkite line, and two pytest guards | **none** |
| BL-014 static pins (`infra/tests/test_public_intake_rate_limit.py`) | post-BL-014 set; pins KongPlugin contents, annotation paths, host names, and the rendered Kong/KIC chart | unchanged — proposal §5 anti-scope: "Changing the BL-014 static pins in `infra/tests/test_public_intake_rate_limit.py`." The new validator is the *runtime* counterpart that catches the silent-drop scenario the static pins cannot see | **none** |
| BL-013 channel tripwire (`infra/tests/test_public_intake_channel_tripwire.py`) | post-SLICE-031 / post-SLICE-032 set | unchanged — INIT-139 is orthogonal; the tripwire is static channel-derivation, the new validator is runtime translation | **none** |
| Kong rendered chart manifest (`gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`) | pre-existing rendered chart with `KONG_ADMIN_LISTEN: "127.0.0.1:8444 http2 ssl, [::1]:8444 http2 ssl"` and `CONTROLLER_KONG_ADMIN_URL: https://localhost:8444` | unchanged — proposal §5 anti-scope; §6 budget excludes "Kubernetes manifest changes". The validator binds to the Admin API exactly as it is rendered today | **none** |
| KongPlugin `public-intake-rate-limit` (`server-manager/public-intake-rate-limit.yaml`) | post-INIT-135 set (`rate-limiting`, `minute: 5`, `hour: 50`, `policy: local`) | unchanged | **none** |
| Adjacent catch-all Ingresses (`server-manager-api`, `web`, `protected-api`) | unannotated by design (proposal "Problem statement") | unchanged | **none** |
| InfisicalSecret runtime contract | unchanged | unchanged | **none** |
| Image refs / Vultr Container Registry / Flux GitRepository / Cloudflare records / Step CA | unchanged | unchanged — proposal §5 anti-scope and §6 budget exclude every remote-runtime concern | **none** |

Risk on §4: **none**. The slice ships no env-var, no migration, no
Pomerium config, no Authentik blueprint, and no OPAL/Cedar policy
edit. Every existing manifest, secret, and policy bundle is
byte-identical after the slice lands. The validator is a pure reader
of live Kong Admin API state; the pytest guards are pure readers of
the new shell file and the Buildkite YAML.

### 5. Kong Admin API access is internal-only (port-forward, not exposed)

| Surface | Pre | Post | Risk |
|---|---|---|---|
| Rendered Kong listener configuration | pre-existing — `KONG_ADMIN_LISTEN: "127.0.0.1:8444 http2 ssl, [::1]:8444 http2 ssl"` at `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml:4124-4125` and again at lines 4285-4286 (KIC sidecar). KIC reaches the Admin API via `CONTROLLER_KONG_ADMIN_URL: https://localhost:8444` (line 4217) with TLS skip-verify | unchanged — proposal §5 anti-scope; §6 budget excludes Kubernetes manifest changes. The Admin listener remains pod-loopback-only after the slice lands | **none** |
| Cluster Service exposing Admin API (`Service/kong-kong-admin` or similar) | absent — the rendered chart binds Admin to `127.0.0.1:8444`, not to a Service. The cluster only exposes `kong-kong-proxy` (the data plane), not the Admin API | unchanged — the validator does NOT create a Service, does NOT patch an existing Service, and does NOT modify the rendered Kong Helm release. Access is through `kubectl port-forward`, which establishes a localhost-only TCP tunnel through the kubelet to the pod's loopback listener; it does not change cluster network policy, Pod resource state, or Kong configuration | **none** |
| NodePort / LoadBalancer on Admin port | absent | absent — the validator does not provision either. `kubectl port-forward` is operator-scope only and ends with the validator process | **none** |
| Network exposure of Admin API beyond pod loopback | not exposed (loopback bind) | not exposed — port-forward is bound to operator localhost via the kubelet's authenticated streaming channel; it carries the operator's kubeconfig credentials and is gone the moment the validator exits (`trap` cleanup per proposal §2 Q3) | **none** |
| TLS verification on the port-forwarded curl | n/a | `--insecure` is used for `curl` (proposal §2 Q3 "Use `--insecure` because the Admin API listener uses self-signed local TLS"). This matches KIC's existing `CONTROLLER_KONG_ADMIN_URL` posture (TLS skip-verify) — no new trust assumption is introduced | **none** — the local TLS material is self-signed by the chart and is intra-pod; the port-forward keeps the connection on operator localhost. `--insecure` is the same posture KIC itself uses inside the same pod |
| Auth on the Admin API call | n/a | none required — the rendered Kong release binds Admin to loopback without authentication, which is the upstream chart's documented posture (the Admin API is intended to be reached only by KIC inside the same pod). The port-forward inherits the operator's kubeconfig auth at the kubelet boundary; no Admin API token is ever placed on disk or in environment | **none** |
| Operator credential exposure | n/a | the validator uses the same `KUBECONFIG_PATH` already used by every other `validate_*_local.sh` script. No new secret, no new token, no new key material, no new SOPS document | **none** |
| Namespace targeted by port-forward | n/a | proposal §2 Q3 locks the canonical command shape `kubectl port-forward deploy/kong-kong -n kong 8444:8444`. The current rendered Kong release is in `kong-system` (per `infra/channels/local.yaml:94 gateway_namespace: kong-system`, `:100 gateway_deployment_name: kong-kong`, and `gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml`). Proposal §2 Q3 explicitly contemplates this: "Hookpoint research or implementation must reconcile that namespace detail before code lands. It must not use the mismatch as a reason to switch to proxy burst behavior." | **finding** — see §"Findings" below; supported-surface impact is **none** because both `kong` and `kong-system` are operator-internal namespaces and neither expansion broadens external exposure |

Risk on §5: **none**. The Admin API surface remains loopback-bound
inside the Kong pod after the slice lands; the validator does not
create or modify any Service, NodePort, or LoadBalancer. Operator
access is mediated through `kubectl port-forward`, which terminates
when the validator process exits via the `trap`. The `--insecure`
curl flag matches the chart's own self-signed local TLS posture and
is the same trust model KIC uses inside the same pod. No new
credential, secret, or token is introduced. The `kong` vs.
`kong-system` namespace detail is a known reconciliation point
flagged by the proposal itself; both candidate namespaces are
operator-internal and neither alters the supported-surface gate's
"internal-only" guarantee.

## Verdict reasoning

LOW.

1. **No public API change (gate §1)**: zero `services/api/`,
   `services/web/`, Discord daemon, or generated-client edits. The
   validator reads live Kong Admin API state through `GET /routes`
   and `GET /routes/<route_id>/plugins`; it neither defines nor
   asserts new HTTP shapes. The pytest guards inspect the new shell
   file and `.buildkite/pipeline-cluster.yml`; they ship no service
   code.
2. **Validator is operator-callable + idempotent (gate §2)**: shape
   matches the existing `validate_*_local.sh --cluster` family.
   Read-only Admin API calls. `trap`-based port-forward cleanup
   per proposal §2 Q3 mirrors the established
   `validate_object_storage_local.sh` and
   `validate_observability_local.sh` patterns. Re-runs are safe by
   construction; no Discord-visible mutation.
3. **CI step is independently runnable from existing cluster lane
   (gate §3)**: a single command line is appended to the existing
   `pr-cluster-merge-readiness-runtime-validators` command block.
   The `agents.queue: cicd-local` queue, 180-minute step timeout,
   tooling preflight, and cluster bring-up are all unchanged. The
   command is also runnable on an operator workstation against the
   existing `humility-local` k3d cluster — same as every other
   `validate_*_local.sh --cluster` script.
4. **No env vars / migrations / Pomerium / Authentik / OPAL changes
   (gate §4)**: proposal §5 anti-scope is unusually explicit and
   §6 budget caps the slice at one shell file (~150-250 LOC), one
   Buildkite line, and two small pytest guards. Existing BL-014
   static pins (`infra/tests/test_public_intake_rate_limit.py`),
   the BL-013 channel tripwire, and every Kong/KIC/Pomerium
   manifest are byte-identical after the slice lands.
5. **Kong Admin API access is internal-only (gate §5)**: the
   rendered Kong chart binds the Admin API to pod loopback
   (`KONG_ADMIN_LISTEN: 127.0.0.1:8444`) and the slice does not
   change that. The validator reaches the Admin API exclusively
   through a per-run `kubectl port-forward` that terminates in the
   `trap`. No Service is created or modified, no NodePort or
   LoadBalancer is provisioned, and no new auth credential is
   introduced. The `--insecure` curl flag matches the chart's
   intra-pod self-signed TLS posture and the same trust model KIC
   itself uses against the same listener.

The slice is a runtime-only smoke that closes the BL-014 silent-drop
gap (manifests stay valid but the controller fails to attach the
plugin). It introduces zero new attack surface, zero new public API
surface, zero new env/migration/manifest footprint, and one
short-lived per-run port-forward that the validator owns end-to-end.

Verdict: **LOW**.

## Findings

One non-blocking reconciliation surfaced by the proposal itself, plus
two implementation-time observations worth carrying into hookpoint /
implementation phases.

### F1 — Kong namespace reconciliation: `kong` (proposal lock) vs `kong-system` (rendered chart)

Proposal §2 Q3 locks the canonical port-forward command shape as:

```bash
kubectl port-forward deploy/kong-kong -n kong 8444:8444 &
```

…but the current local rendered manifests place the Kong release in
`kong-system`:

- `infra/channels/local.yaml:94 gateway_namespace: kong-system`
- `infra/channels/local.yaml:100 gateway_deployment_name: kong-kong`
- `infra/channels/local.yaml:101 proxy_service_name: kong-kong-proxy`
- `infra/tests/fixtures/contracts/kong_ingress_contract.yml:19-20`
- `infra/tests/validate_auth_stack_local.sh:286` references
  `kong-kong-proxy.kong-system.svc.cluster.local`
- `infra/tests/test_public_intake_rate_limit.py:96-100` asserts the
  rendered `Deployment/kong-kong` is in `namespace: kong-system`

The proposal is explicit about how to handle this: "Hookpoint
research or implementation must reconcile that namespace detail
before code lands. It must not use the mismatch as a reason to
switch to proxy burst behavior." This is a finding for hookpoint /
implementation, not a supported-surface blocker — both `kong` and
`kong-system` are operator-internal namespaces, and either choice
keeps the Admin API loopback-bound inside the Kong pod. The
supported-surface gate's "internal-only" guarantee holds either way.

### F2 — Cluster bring-up uses `--cluster-only`; runtime smoke needs reconciled state

The cluster lane runs `infra/scripts/bring-up-local-channel.sh
--channel local --force --cluster-only`
(`.buildkite/pipeline-cluster.yml:21`), which the problem map flags
as Flux-skip:

> "the current cluster lane calls bring-up with `--cluster-only`,
> which skips Flux post-install. The smoke cannot be meaningful
> against an empty k3d cluster."

The proposal places the new validator "after Kong, TLS/DNS,
auth/server-manager, or existing readiness validators have made the
live route state meaningful" (§3 "Modified file" / Substrate). That
ordering presumes the existing five validators in the
`pr-cluster-merge-readiness-runtime-validators` block already
produce or rely on a reconciled state today. This is an
implementation-time concern: if the new validator runs before KIC
has reconciled the public-intake KongPlugin annotation into Kong
Routes, the route-pagination loop must wait, not fail. Proposal §3
"Substrate / New file" explicitly lists "Waits for Kong deployment
availability" as a required step; implementer must extend that
readiness wait to cover route visibility for the five expected
public-intake host/path combinations before asserting plugin
presence. This is *not* a supported-surface gate concern — the gate
asks "is the surface internal-only," not "is the runtime state
ready." The §2 Q5 plugin assertions remain idempotent retries
against the same Admin API.

### F3 — Pytest guard scope discipline

Proposal §3 "Test-only guard files" allows TG-2 and TG-3 to "modify
existing pytest guard files under `infra/tests/`" rather than always
adding new files. Implementer should prefer extending an existing
Buildkite-pipeline guard test if one already owns cluster-lane
assertions (proposal §6 "Diff budget" suggests this), keeping the
diff small. The supported-surface gate is unaffected either way:
both options stay inside `infra/tests/` and ship no production code.

## Output checklist (proposal §"Check" criteria)

1. ✓ **No public API change** — zero edits to `services/api/`,
   `services/web/`, generated clients, Discord daemon, contracts,
   request/response models, dependencies, or error mappers.
2. ✓ **Validator is operator-callable + idempotent** — shape
   matches the existing `validate_*_local.sh --cluster` family;
   read-only Admin API; `trap`-based port-forward cleanup;
   `KUBECONFIG_PATH` default unchanged; same `PASS:` / `FAIL:` /
   `ERROR:` output contract.
3. ✓ **CI step is independently runnable from existing cluster
   lane** — one command line appended to
   `pr-cluster-merge-readiness-runtime-validators`; same
   `cicd-local` queue, same 180-minute timeout, same tooling
   preflight, same cluster bring-up step. Operator can run the
   validator outside Buildkite via the same `--cluster` flag.
4. ✓ **No env vars / migrations / Pomerium / Authentik / OPAL
   changes** — proposal §5 anti-scope and §6 budget exclude every
   one of these surfaces; existing BL-014 static pins, BL-013
   channel tripwire, and all Kong/KIC/Pomerium/Authentik
   manifests are byte-identical post-slice.
5. ✓ **Kong Admin API access is internal-only (port-forward, not
   exposed)** — rendered chart binds Admin to `127.0.0.1:8444`;
   the slice does not change that. No Service, NodePort, or
   LoadBalancer is created or modified. Access is per-run
   `kubectl port-forward` only, terminated by the `trap` on
   validator exit. `--insecure` curl flag matches the chart's
   intra-pod self-signed TLS posture and KIC's own existing
   trust model against the same listener. Namespace
   reconciliation between `kong` (proposal lock) and
   `kong-system` (rendered chart) is a hookpoint / implementation
   task and does not change the internal-only guarantee.

SUPPORTED_SURFACE_DONE: plans/risk/init-139-supported-surface.md
