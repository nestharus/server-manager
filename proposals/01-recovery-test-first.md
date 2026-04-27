# Recovery — test-first reset of INIT-100..119

## Scope summary

This proposal ships a test-first recovery plan for the INIT-100..119
deployment substrate. It repairs the operator-webhook NetworkPolicy
outage first seen in Crossplane through a single Phase 6 cycle, promotes
the already-verified but currently-dead service and runtime validators
into CI, rebuilds the violated Phase 6
evidence for CONTINUE layers INIT-101..113 and INIT-117, fully
decomposes the high-risk INIT-114/115/116/118/119 layers, modernizes the
legacy root-daemon test surface, and adds Buildkite blocking wrappers
around advisory red/green/process-tree verdicts so future violations fail
before merge. This closes the R1 posture gaps for legacy tests and gate
blocking. Addresses AUDIT-A2, AUDIT-A3, SHORTCUT-S1, and
SUPPORTED-SURFACE-1.

This proposal does not add product features, does not deploy to real
Vultr, does not start INIT-120+, does not rewrite working implementation
for aesthetic reasons, and does not choose 6c fixes in advance. The
proposal defines the recovery contract and slice order. Step 6c agents
may change code only after independent Step 6b tests, red-phase evidence,
and the applicable gate artifacts exist.

## Existing-state risk profile (problem map)

- What is actually deployed: 18 INITs of implementation code beyond the
  INIT-100 reset baseline, with INIT-101..119 all carrying blocking
  Phase 6 process violations. The process-tree audit found missing
  Step 6b output indexes, missing red-phase gates, missing green-phase
  gates, missing Phase 6 process-tree audits, and missing supported-
  surface risk artifacts across the whole INIT-101..119 sequence.

- What is actually tested: 141 test files were audited. The primary
  verdicts are 27 VERIFIED_BEHAVIOR files, 52 CAPTURED_BEHAVIOR files,
  16 STRUCTURAL files, 44 DEAD files, and 2 HARMFUL findings. In
  percentage terms, the suite is 19% VERIFIED, 37% CAPTURED, 11%
  STRUCTURAL, 31% DEAD, and 1% HARMFUL. The single biggest constraint is
  not absence of all tests; it is that many good tests are outside the
  main Buildkite lane.

- What is actually broken: Kubernetes admission cannot reach the
  Crossplane validating webhook in the local cluster. The RCA shows the
  Crossplane controller is Running, the `crossplane-webhooks` Service
  resolves to the expected endpoint, and the webhook listener is present,
  but pod-to-pod and API-server proxy traffic to the webhook endpoint is
  rejected after INIT-117 introduced a namespace-wide NetworkPolicy that
  only allows observability ingress. The current branch also leaves about
  half of runtime-capable validators dead or static-only from CI.

- What works as intended even with Phase 6 violations: the audit found a
  real 19% VERIFIED test surface, especially in `services/api/tests/`.
  Runtime bring-up evidence also reached a meaningful state before the
  webhook failure: 57 pods Running and the Infisical bootstrap path
  reaching `ReadyToSyncSecrets=True`. Several shell validators are
  behavior-shaped and useful when run against a cluster, including
  object-storage round trip, TLS/DNS issuance, Crossplane claim
  readiness, NetworkPolicy denial, registry push/pull, and runtime
  application checks.

- Adjacent surfaces inside the blast radius: `.buildkite/pipeline.yml`,
  `.buildkite/e2e-fullstack.yml`, `infra/tests/**`,
  `infra/tests/e2e/**`, `services/api/tests/**`,
  `services/discord/tests/**`, `services/web/tests/**`,
  `gitops/channels/local/**`, `infra/scripts/**`,
  `infra/schemas/**`, `containers/**`, and the workflow artifacts under
  `research/`, `plans/audit-history/`, `plans/process-tree-audits/`,
  `risk/`, and per-slice scratch directories.

- Supported local surface: the supported surface for this recovery is
  local-first deployment and validation. The proof target is a clean
  local cluster driven by the existing local channel, with CI lanes that
  run the service suites, static validators, cluster-equipped runtime
  validators, and the full-stack E2E suite when the cluster lane is
  selected. The cluster-equipped lane is either
  `.buildkite/pipeline-cluster.yml` or an equivalent
  `.buildkite/pipeline.yml` step with an `if` condition tied to
  PR-merge-readiness for Phase 6 recovery slices whose test-intent track
  needs cluster runtime. The nightly lane is either
  `.buildkite/pipeline-nightly.yml` or an equivalent scheduled trigger.
  Real remote apply remains out of scope. Addresses AUDIT-A1 and
  SUPPORTED-SURFACE-2.

- Current net-value case: this recovery clearly reduces current-state
  risk because the branch is already relying on code whose validators are
  either captured, dead, or not authored through separate Phase 6 agents.
  The added blast radius is CI churn and validator rewrites. That cost is
  smaller than continuing to treat captured/static validators as evidence
  for a live deployment substrate.

## Audit finding disposition

| Finding | Disposition |
|---|---|
| Phase 6 same-invocation test/code execution for INIT-101..119 | Bound to SLICE-R.01 and SLICE-R.04..R.25 through required Step 6a/6b/6c separation and process-tree audit. |
| Missing Step 6b output index for INIT-101..119 | Bound to every Phase 6 recovery slice; each slice must emit `${scratch_dir}/phase6/step6b-output-index.md`. |
| Missing Step 6c consumption evidence | Bound to every code-agent slice; Step 6c logs must list Step 6b index and output test paths before product-code edits. |
| red-phase-gate skipped for INIT-101..119 | Bound to every test-first slice; RED, MIXED, ALL_GREEN, or BLOCKED must be recorded before code consumption. |
| green-phase-gate skipped for INIT-101..119 | Bound to every Step 6c slice; green report must run after implementation and before CodeRabbit. |
| Phase 6 process-tree-auditor skipped before CodeRabbit | Bound to every slice that reaches CodeRabbit; process-tree-auditor must pass or produce explicit stop evidence. |
| Phase 4 supported-surface risk missing | Bound to Phase 4 for this proposal; all four risks plus risk-gate process-tree audit are required before Phase 5. |
| Phase 4 process-tree-auditor skipped historically | Bound to SLICE-R.24 as a blocking Buildkite verdict wrapper around advisory gate reports and to Phase 4 execution of this recovery. Addresses AUDIT-A2 and SHORTCUT-S1. |
| Phase 0 RCA skipped on prior bug-shaped work | Bound to behavior-investigator inputs for INIT-106, INIT-107, INIT-110, INIT-111, INIT-114, INIT-118, and to SLICE-R.01 for the current Crossplane RCA. |
| Crossplane/CNPG/cert-manager operator webhook unreachable pattern | Bound to SLICE-R.01. Addresses SUPPORTED-SURFACE-1. |
| 44 DEAD test files | Bound to SLICE-R.02, SLICE-R.03, SLICE-R.05..R.19, and SLICE-R.25 depending on layer and legacy-test disposition. |
| 52 CAPTURED files | Bound to behavior-investigation and rewrite work in SLICE-R.04..R.19. |
| 16 STRUCTURAL files | Bound to SLICE-R.02 for service CI wiring and to SLICE-R.04/R.14..R.18 when structural tests overlap recovered layer contracts. |
| Two HARMFUL findings | Bound to SLICE-R.04, SLICE-R.02, and SLICE-R.25: `test_local_buildkite_pipeline.py` step-list assertion is rewritten; legacy `tests/test_discord_cli.py` is classified before it is modernized, migrated, or deleted/replaced. Addresses AUDIT-A3. |
| `services/api/tests/**` not run by mainline CI | Bound to SLICE-R.02. |
| `services/discord/tests/**` not run by mainline CI | Bound to SLICE-R.02 with captured/mock-heavy tests treated as rewrite candidates, not automatic VERIFIED promotion. |
| `services/web/tests/compat.spec.ts` not run by mainline CI | Bound to SLICE-R.02 and SLICE-R.22. |
| Runtime validators run static-only or not at all | Bound to SLICE-R.03 and per-layer runtime slices. |
| INIT-119 E2E suite entirely DEAD/WIP | Bound to SLICE-R.23, not accepted as canonical validation. |
| Root legacy daemon tests are captured/structural/HARMFUL | Bound to SLICE-R.25 for KEEP_AS_IS / MODERNIZE / MIGRATE / DELETE_AND_REWRITE classification and CI wiring of surviving tests; still not treated as product-service proof without modernization. Addresses AUDIT-A3. |

## Test-intent track (per layer)

### L01 cluster substrate — INIT-101

- Intended behavior: local platform bootstrap creates a reproducible
  control cluster substrate and handoff contract without absorbing Flux,
  Crossplane, CI, identity, or application workload ownership.
- Risk it reduces: a bootstrap that only matches copied resolver strings
  could drift from the actual cluster shape and still pass static checks.
- Selected test level: component for channel/schema contract; integration
  for k3d cluster reachability and node readiness.
- Fixture source / fixture application point: dedicated channel fixture
  file under `infra/tests/fixtures/channels/` plus k3d cluster fixture in
  the runtime harness; test bodies do not construct durable cluster
  fixture state.
- Existing test and verdict: `infra/tests/validate_platform_bootstrap.sh`
  is DEAD/CAPTURED; `infra/tests/e2e/tests/01-cluster-up.sh` is DEAD but
  behavior-shaped.
- Recovery slice: SLICE-R.05.

### L02 GitOps foundation — INIT-102

- Intended behavior: Git is desired state, Flux is the sole reconciler,
  each cluster has one scoped Flux root, and CI validates without
  mutating in-cluster state directly.
- Risk it reduces: a second deployment loop or overbroad Flux root could
  mutate the cluster outside the desired-state boundary.
- Selected test level: integration for Flux source and Kustomization
  readiness; component for SOPS boundary lint negative case.
- Fixture source / fixture application point: Git fixture repository and
  SOPS sentinel fixture applied by the harness outside test bodies.
- Existing test and verdict: `infra/tests/e2e/tests/02-flux-reconciles.sh`
  is DEAD/VERIFIED; SOPS assertions are buried in
  `validate_platform_bootstrap.sh` and need contract extraction.
- Recovery slice: SLICE-R.06.

### L03 runtime secrets — INIT-103

- Intended behavior: Infisical operator syncs runtime secrets from the
  approved local project/path boundary into Kubernetes without committing
  plaintext secrets outside the bootstrap allowance.
- Risk it reduces: a secret path or plaintext leak can appear valid if
  the validator only checks committed literal strings.
- Selected test level: integration for operator `ReadyToSyncSecrets` and
  generated Kubernetes Secret data; component for plaintext boundary
  lint.
- Fixture source / fixture application point: encrypted sentinel fixture
  and Infisical bootstrap fixture applied by the runtime harness.
- Existing test and verdict: `infra/tests/e2e/tests/04-infisical-runtime.sh`
  is DEAD/VERIFIED; bootstrap lint coverage is indirect.
- Recovery slice: SLICE-R.07.

### L04 object storage — INIT-104

- Intended behavior: local S3-compatible object storage supports bucket
  creation, write, read, restart durability, and download equality for
  platform storage paths.
- Risk it reduces: MinIO may be installed but unable to persist or return
  stored objects after restart.
- Selected test level: integration.
- Fixture source / fixture application point: object payload fixture and
  bucket name fixture in validator fixture files; credentials supplied by
  runtime harness.
- Existing test and verdict: `infra/tests/validate_object_storage_local.sh`
  is DEAD/VERIFIED; `infra/tests/e2e/tests/05-storage.sh` is DEAD wrapper.
- Recovery slice: SLICE-R.08.

### L05 TLS/DNS — INIT-105

- Intended behavior: local certificate and DNS substrate issues a sample
  Certificate, makes the selected hostname resolvable in-cluster, and
  keeps production ACME/DNS promotion out of the local proof.
- Risk it reduces: ingress-dependent layers can claim readiness even
  though certificate issuance or DNS resolution is absent.
- Selected test level: integration.
- Fixture source / fixture application point: hostname and Certificate
  fixture applied by the TLS/DNS validator; cluster DNS proof pod supplied
  by runtime harness.
- Existing test and verdict: `infra/tests/validate_tls_dns_local.sh` is
  DEAD/VERIFIED; `infra/tests/e2e/tests/06-tls-dns.sh` is DEAD wrapper.
- Recovery slice: SLICE-R.09.

### L06 app cluster provisioning — INIT-106

- Intended behavior: Crossplane core and provider expose an `AppCluster`
  claim contract; a local claim reaches Ready and publishes the standard
  connection/handoff contract for downstream cluster bootstrap.
- Risk it reduces: a cluster claim can appear syntactically valid while
  Crossplane cannot reconcile, update, or publish usable connection
  state.
- Selected test level: integration and e2e for local claim readiness.
- Fixture source / fixture application point: claim manifest fixture and
  child-cluster kubeconfig fixture applied by validator harness.
- Existing test and verdict: `infra/tests/validate_app_clusters_local.sh`
  is DEAD/VERIFIED; `infra/tests/e2e/tests/07-app-cluster.sh` is DEAD
  wrapper.
- Recovery slice: SLICE-R.10.

### L07 cluster security — INIT-107

- Intended behavior: restricted Pod Security Standards, namespace-level
  NetworkPolicy denial, and RBAC denial are enforced in the local
  cluster while allowing explicitly required platform communication.
- Risk it reduces: permissive security posture can be hidden by static
  manifests and later break or overallow workloads.
- Selected test level: integration.
- Fixture source / fixture application point: denied privileged Pod,
  denied network probe, and RBAC subject fixtures live in validator
  fixture modules or shell fixture data.
- Existing test and verdict: `infra/tests/validate_cluster_security_local.sh`
  is DEAD/VERIFIED; `infra/tests/e2e/tests/08-cluster-security.sh` is
  DEAD wrapper.
- Recovery slice: SLICE-R.11.

### L08 image registry and delivery — INIT-108

- Intended behavior: Buildkite/local tooling can build an image, push it
  to the local channel registry, run it from the cluster, and observe the
  expected runtime proof from the container.
- Risk it reduces: app workload layers may pass manifest checks while
  image delivery is broken.
- Selected test level: integration.
- Fixture source / fixture application point: sample container fixture
  under `containers/samples/` and registry/channel fixture applied by the
  delivery validator.
- Existing test and verdict:
  `infra/tests/validate_container_delivery_local.sh` is DEAD/VERIFIED;
  `infra/tests/e2e/tests/09-image-registry.sh` is DEAD wrapper.
- Recovery slice: SLICE-R.12.

### L09 Buildkite CI/CD — INIT-109

- Intended behavior: local CI has explicit pipeline artifacts, validates
  supported steps through a local runner, sources agent token material
  from Infisical, and does not pretend Buildkite SaaS has an offline YAML
  emulator.
- Risk it reduces: tests can lock an exact step-key list while failing
  to prove that CI executes the supported command/wait/artifact contract.
- Selected test level: unit/component for runner semantics; integration
  for local agent smoke and image build lane.
- Fixture source / fixture application point: pipeline YAML fixtures
  under dedicated test data; Buildkite token fixture supplied via
  Infisical/runtime harness.
- Existing test and verdict:
  `infra/tests/test_local_buildkite_pipeline.py` is CAPTURED-mixed with
  one HARMFUL step-list assertion; `validate_buildkite_cicd_local.sh` is
  DEAD/CAPTURED with useful gated runtime portions.
- Recovery slice: SLICE-R.13.

### L10 Kong ingress — INIT-110

- Intended behavior: Kong Gateway and KIC provide the platform ingress
  layer; a sample HTTPS route through Kong reaches the MinIO health
  endpoint with DNS and certificate readiness proved.
- Risk it reduces: captured chart/version assertions can pass while the
  actual host route, TLS termination, or backend reachability fails.
- Selected test level: component for channel contract; integration for
  DNS/cert/Kong curl.
- Fixture source / fixture application point: host/certificate/Ingress
  fixture applied by the validator; curl proof pod created by runtime
  harness.
- Existing test and verdict: `infra/tests/test_kong_ingress_contract.py`
  is CAPTURED; `validate_kong_ingress_local.sh` is DEAD/CAPTURED-mixed
  with a VERIFIED runtime curl portion.
- Recovery slice: SLICE-R.14.

### L11 data plane — INIT-111

- Intended behavior: CloudNativePG and Atlas provide a sample PostgreSQL
  data plane; the local proof waits for operator/cluster readiness,
  applies migrations, and connects with `psql`.
- Risk it reduces: a database stack can render successfully while
  migrations or connectivity are broken.
- Selected test level: integration, with future failover proof recorded
  as residual unless the contract slice includes it.
- Fixture source / fixture application point: migration fixture, database
  credentials fixture, and `psql` client harness outside test bodies.
- Existing test and verdict: `validate_data_plane_local.sh --static-only`
  is CAPTURED in CI; runtime mode would be VERIFIED but is not run.
- Recovery slice: SLICE-R.15.

### L12 backup / DR — INIT-112

- Intended behavior: local backup configuration creates a scheduled
  backup and supports a deterministic restore drill where known data is
  inserted, backed up, restored into a fresh cluster, and verified.
- Risk it reduces: a `ScheduledBackup` manifest can exist while restore
  is impossible or untested.
- Selected test level: integration/e2e restore drill.
- Fixture source / fixture application point: seed SQL fixture and manual
  Backup/restore-cluster fixture applied by validator harness.
- Existing test and verdict: `infra/tests/test_backup_dr_contract.py` is
  CAPTURED; `validate_backup_dr_local.sh` is CAPTURED when static, with
  the restore drill requirement underverified.
- Recovery slice: SLICE-R.16.

### L13 application workloads — INIT-113

- Intended behavior: API, Discord daemon, database migration, secrets,
  image delivery, MinIO bucket bootstrap, and Kong route form a focused
  local application workload proof.
- Risk it reduces: manifests can point at copied image tags while pods
  cannot start, connect to the database, or serve through ingress.
- Selected test level: integration and e2e.
- Fixture source / fixture application point: image tag fixture supplied
  by build step, API/Discord runtime fixture applied by workload
  validator, database seed fixture outside test body.
- Existing test and verdict:
  `infra/tests/test_application_workloads_contract.py` is CAPTURED;
  `validate_application_workloads_local.sh --static-only` is CAPTURED in
  CI; runtime mode is not mainline.
- Recovery slice: SLICE-R.17.

### L14 auth stack — INIT-114

- Intended behavior: Authentik, Pomerium, OPAL/Cedar, and protected API
  proof route compose into an OIDC-authenticated flow where missing
  identity returns 401, Cedar deny returns 403, Cedar outage returns 503,
  and authorized identity reaches the protected proof.
- Risk it reduces: a security layer can assert chart pins while the
  actual OIDC route, Pomerium headers, or Cedar decision path is wrong.
- Selected test level: component for API authorization contract;
  integration/e2e for Pomerium route and Cedar agent behavior.
- Fixture source / fixture application point: identity header fixture,
  Cedar decision fixture, OIDC/Pomerium route fixture, and Playwright
  auth fixture outside test bodies.
- Existing test and verdict: `infra/tests/test_auth_stack_contract.py`
  and `validate_auth_stack_local.sh --static-only` are CAPTURED;
  `infra/tests/e2e/tests/15-auth-stack.sh` is DEAD.
- Recovery slice: SLICE-R.18, DECOMPOSE.

### L15 access policy — INIT-115

- Intended behavior: Cedar policy allows and denies principals,
  resources, and actions according to the explicit matrix; break-glass
  and credential rotation are bounded by the access policy contract.
- Risk it reduces: literal policy-id assertions can pass while the policy
  authorizes the wrong actor or denies the intended one.
- Selected test level: unit/component for Cedar matrix evaluation;
  integration for policy bundle load and protected endpoint decision.
- Fixture source / fixture application point: Cedar matrix fixture and
  principal/resource/action fixture data generated from contract, not
  implementation.
- Existing test and verdict: `infra/tests/test_access_policy_contract.py`
  and `validate_access_policy_local.sh --static-only` are CAPTURED.
- Recovery slice: SLICE-R.19, DECOMPOSE.

### L16 tenant isolation — INIT-116

- Intended behavior: tenant namespaces, RBAC, NetworkPolicy, Infisical
  paths, S3 prefixes, and Cedar tenant resource selectors deny cross-
  tenant access while allowing same-tenant local/dev flows.
- Risk it reduces: a channel resolver can emit the expected label dict
  while tenant A can read tenant B's namespace, S3 prefix, DB surface, or
  policy resource.
- Selected test level: component for Cedar tenant decisions; integration
  for namespace/RBAC/NetworkPolicy/secret denial.
- Fixture source / fixture application point: tenant fixture set
  (`sample-local`, `sample-dev`, `other-local`) generated outside test
  bodies by the tenant spawn harness.
- Existing test and verdict: `infra/tests/test_tenant_isolation_contract.py`
  and `validate_tenant_isolation_local.sh --static-only` are CAPTURED;
  no in-CI negative-path proof exists.
- Recovery slice: SLICE-R.20, DECOMPOSE.

### L17 observability — INIT-117

- Intended behavior: Prometheus, Grafana, Alertmanager, OTel Collector,
  and Loki provide local scrape/log/alert proof for platform components
  without changing tenant or policy semantics.
- Risk it reduces: ServiceMonitor and dashboard manifests can exist
  while no metrics, logs, or alerts are actually observable.
- Selected test level: integration.
- Fixture source / fixture application point: sample alert fixture, sample
  log fixture, Prometheus target query fixture, and dashboard provisioning
  fixture applied by runtime validator.
- Existing test and verdict: `infra/tests/test_observability_contract.py`
  and `validate_observability_local.sh --static-only` are CAPTURED in CI;
  runtime mode contains useful scrape/log/alert checks but is gated.
- Recovery slice: SLICE-R.21.

### L18 web UI substrate — INIT-118

- Intended behavior: the web app routes, submits forms, respects
  auth-gated API behavior, renders expected application surfaces, and
  keeps FontAwesome/Ark/TanStack integration working under local ingress.
- Risk it reduces: package/version checks and demo heading assertions can
  pass while the web UI has no reachable pod, no working route, or no
  valid auth/API interaction.
- Selected test level: component for UI controls and form renderer; e2e
  for routing, auth gate, submit, and ingress reachability.
- Fixture source / fixture application point: form schema fixture,
  identity fixture, API fake/recording fixture, and Playwright route
  fixture outside test bodies.
- Existing test and verdict: `infra/tests/test_web_ui_contract.py` and
  `validate_web_ui_local.sh --static-only` are CAPTURED;
  `services/web/tests/compat.spec.ts` is DEAD/CAPTURED.
- Recovery slice: SLICE-R.22, DECOMPOSE.

### L19 cross-cutting E2E — INIT-119

- Intended behavior: the full local stack can be brought up from a clean
  cluster and prove the cross-layer contracts from cluster bootstrap
  through web UI, auth, policy, tenant isolation, observability, and app
  runtime paths.
- Risk it reduces: a same-run WIP E2E suite can validate the broken
  behavior it observed or skip the supported path while looking green.
- Selected test level: end-to-end.
- Fixture source / fixture application point: `infra/tests/e2e/lib/`
  harness fixtures, Playwright fixtures, per-layer contracts, and local
  cluster fixture generated by `run-fullstack.sh`.
- Existing test and verdict: all 19 `infra/tests/e2e/tests/*.sh` files
  are DEAD; framework files are preserved as infrastructure but tests are
  rebuilt from the per-layer contracts.
- Recovery slice: SLICE-R.23, DECOMPOSE.

### App service suites

- Intended behavior: API, Discord, and web service tests exercise their
  public contracts in mainline CI rather than living as orphan suites.
- Risk it reduces: the highest-quality API tests remain invisible to
  commit gating, while captured/mocked Discord and web tests are mistaken
  for behavioral evidence.
- Selected test level: unit, component, integration, and e2e according
  to each suite.
- Fixture source / fixture application point: existing service fixtures,
  testcontainers Postgres fixtures, FakeApiClient transport fixtures,
  Playwright fixtures, and service-specific conftest modules.
- Existing test and verdict: `services/api/tests/**` is mostly
  DEAD/VERIFIED; `services/discord/tests/**` is DEAD with many CAPTURED
  mock-and-verify tests; `services/web/tests/compat.spec.ts` is
  DEAD/CAPTURED.
- Recovery slice: SLICE-R.02 and follow-up layer slices where tests need
  rewriting.

## Slice decomposition (binding)

### SLICE-R.01 — Operator webhook reachability Phase 6

- Owner agent: orchestrator for Step 6a contract; test-writer for Step
  6b; red-phase-gate; separate code agent for Step 6c; green-phase-gate;
  process-tree-auditor.
- Dependencies: Phase 4 risk gates for this proposal; Phase 5 hookpoint
  research for operator webhook NetworkPolicies, rendered manifests, and
  validator locations.
- Contract: operator validating/mutating webhook Services affected by
  INIT-117's `allow-observability-scrape` empty-pod-selector
  NetworkPolicy pattern must be reachable from the Kubernetes admission
  path and from in-cluster same-namespace probes while preserving
  intended observability scrape access. The required namespace surface is
  `crossplane-system`, `cnpg-system`, `cert-manager`, and any other
  namespace where the same INIT-117 policy pattern was applied.
  Addresses SUPPORTED-SURFACE-1.
- Acceptance criteria:
  - Step 6a writes the reachability contract from
    `research/01-rca-crossplane-webhook-unreachable.md`.
  - Step 6b emits tests that prove webhook endpoint reachability,
    admission dry-run behavior, and absence of unintended same-namespace
    isolation for Crossplane, CNPG, cert-manager, and any other namespace
    carrying the same empty-selector observability policy pattern.
  - red-phase-gate records CONFIRMED_RED or MIXED for the new tests; if
    ALL_GREEN, behavior-investigator explains why current HEAD already
    satisfies intended reachability.
  - Step 6c applies the minimal NetworkPolicy adjustment needed in each
    affected operator-webhook namespace without broadening unrelated
    namespace access.
  - green-phase-gate records CONFIRMED_GREEN or a documented BLOCKED
    state that stops downstream consumption.
  - process-tree-auditor verifies separate 6b/6c invocations and Step 6c
    consumption of the Step 6b output index.
- Fixture source: operator webhook Service fixtures, probe pod fixture,
  and admission dry-run fixture under `infra/tests/fixtures/operator-webhooks/`
  or equivalent dedicated harness fixture.
- Anti-scope: no Crossplane/CNPG/cert-manager upgrade, no provider replacement, no
  broad security-policy redesign, no real Vultr deployment.

### SLICE-R.02 — Mainline CI service-suite wiring

- Owner agent: orchestrator for contract; test-writer only if CI
  contract tests are missing; code agent for pipeline wiring; gate
  agents for red/green where Python tests change.
- Dependencies: none after Phase 5 hookpoints.
- Contract: `.buildkite/pipeline.yml` runs `services/api/tests/`,
  `services/discord/tests/`, and `services/web` tests in appropriate
  steps, with service dependencies explicitly installed and artifacts
  preserved.
- Acceptance criteria:
  - API suite becomes mainline CI-gated and the existing DEAD/VERIFIED
    files are promoted to VERIFIED operational status.
  - Buildkite pre-flight verifies Docker availability for
    testcontainers Postgres before the API suite is counted as CI-gated;
    missing Docker is BLOCKED, not green. Addresses SHORTCUT-S8 watch
    signal.
  - Discord suite becomes mainline CI-gated but CAPTURED tests are not
    promoted to VERIFIED merely because they run.
  - Web test command runs the existing Playwright/Vitest-compatible
    suite or records a contract-correct BLOCKED reason if the current
    toolchain cannot run without a Phase 6 web recovery slice.
  - The HARMFUL Buildkite step-list assertion is removed or rewritten as
    behavioral pipeline validation within SLICE-R.04.
  - `tests/test_discord_cli.py` is not treated as evidence for the new
    service architecture.
- Fixture source: existing `services/*/tests/conftest.py`,
  testcontainers setup, package manager lockfiles, and Buildkite service
  environment.
- Anti-scope: no rewriting of API behavior, no new Discord product
  features, no UI feature expansion.

### SLICE-R.03 — Cluster-equipped runtime validator CI lane

- Owner agent: orchestrator; code agent for CI lane; process-tree-auditor
  for CI-gate integration; coverage-auditor for before/after audit.
- Dependencies: SLICE-R.01 when Crossplane webhook reachability blocks
  local full-stack reconciliation.
- Contract: runtime validators that need a cluster run on a cluster-
  equipped Buildkite lane rather than being limited to `--static-only`.
  The lane mechanism is `.buildkite/pipeline-cluster.yml` or an
  equivalent `.buildkite/pipeline.yml` step with an `if` condition on
  PR-merge-readiness for Phase 6 recovery branches. Nightly coverage is
  `.buildkite/pipeline-nightly.yml` or an equivalent scheduled trigger.
  Addresses AUDIT-A1 and SUPPORTED-SURFACE-2.
- Acceptance criteria:
  - `validate_object_storage_local.sh`,
    `validate_tls_dns_local.sh`, `validate_app_clusters_local.sh`,
    `validate_cluster_security_local.sh`,
    `validate_container_delivery_local.sh`, and later recovered runtime
    validators have an explicit cluster lane.
  - The cluster lane is mandatory on every Phase 6 recovery slice whose
    test-intent track depends on cluster runtime; unrelated slices use
    scheduled or manual cluster runs.
  - The nightly scheduled lane runs the aggregate cluster/runtime suite
    independently of PR gating.
  - Static-only steps remain only where they verify static contracts and
    are not presented as runtime proof.
  - Visible skips such as missing browser or missing cluster are red or
    blocked signals for the lane, not green success.
  - coverage-auditor before/after shows DEAD runtime validators moved to
    VERIFIED or intentionally blocked with documented cause.
- Fixture source: local k3d cluster fixture from E2E harness and
  validator-specific runtime fixtures.
- Anti-scope: no remote cluster provisioning, no production Buildkite
  organization setup.

### SLICE-R.04 — Rewrite the captured contract pytests

- Owner agent: behavior-investigator for intended behavior; test-writer
  for tests; red-phase-gate; code agent only for removal of harmful or
  invalid tests; green-phase-gate; coverage-auditor.
- Dependencies: Phase 5 hookpoint research for test locations.
- Contract: the eight captured contract pytest groups are rewritten from
  original proposals, commits, and product goals, not from current
  resolver output.
- Acceptance criteria:
  - Rewrite or delete captured assertions in L01 and L09-L18 contract
    pytests where they only compare implementation to implementation.
  - `infra/tests/test_local_buildkite_pipeline.py` no longer asserts an
    exact ordered step-key snapshot.
  - Every retained test has a risk annotation that names source proposal
    or assumption-register item.
  - red-phase-gate treats ALL_GREEN as suspicious unless
    behavior-investigator confirms the current implementation already
    satisfies the intended contract.
  - coverage-auditor records CAPTURED -> VERIFIED, CAPTURED -> removed,
    or residual risk for every touched file.
- Fixture source: dedicated YAML/JSON fixtures for channel examples and
  negative cases; no same-file durable fixtures inside test bodies.
- Anti-scope: no product implementation fixes except deleting or
  replacing invalid tests.

### SLICE-R.05 — INIT-101 cluster substrate recovery

- Owner agent: behavior-investigator, test-writer, red-phase-gate, code
  agent if needed, green-phase-gate, process-tree-auditor.
- Dependencies: SLICE-R.02 for CI visibility.
- Contract: the local platform cluster bootstrap can be validated from
  the Platform Bootstrap proposal and handoff criteria.
- Acceptance criteria:
  - Independent tests verify cluster reachability, node readiness, and
    stable bootstrap handoff.
  - `validate_platform_bootstrap.sh` captured portions are either
    replaced, narrowed to structural checks, or mapped to explicit
    residuals.
  - Runtime cluster proof is available in the cluster-equipped lane.
  - Any hidden provider/lockfile behavior without RCA is escalated before
    6c consumption.
- Fixture source: local channel fixture and k3d cluster fixture.
- Anti-scope: no Flux installation and no Crossplane expansion in this
  slice.

### SLICE-R.06 — INIT-102 GitOps/SOPS recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.05.
- Contract: Flux reconciles only its approved root, restores desired
  state after mutation, and SOPS boundary lint catches plaintext leaks.
- Acceptance criteria:
  - Tests prove GitRepository/Kustomization Ready state.
  - A drift mutation fixture proves Flux reconciliation restores the
    desired state or documents a bounded residual if too expensive.
  - A negative plaintext fixture proves the SOPS boundary lint fails on a
    leak.
  - Existing E2E wrapper is promoted only after mainline CI runs it.
- Fixture source: Git repo fixture, plaintext leak fixture, SOPS sentinel
  fixture.
- Anti-scope: no new GitOps topology.

### SLICE-R.07 — INIT-103 Infisical recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.06.
- Contract: local runtime secrets sync through Infisical and produce
  usable Kubernetes Secret data without plaintext expansion.
- Acceptance criteria:
  - Operator deployment and `InfisicalSecret` reach ready status.
  - Generated Secret has non-empty data from the fixture path.
  - Negative boundary test proves plaintext leak detection where the
    original proposal requires it.
  - DEAD/VERIFIED E2E secret proof becomes CI-visible.
- Fixture source: encrypted secret sentinel and Infisical project/path
  fixture.
- Anti-scope: no new secret platform or production federation.

### SLICE-R.08 — INIT-104 object-storage recovery

- Owner agent: behavior-investigator for contract confirmation;
  test-writer only for missing annotations/output index; code agent for
  CI/harness fixes if needed.
- Dependencies: SLICE-R.03.
- Contract: MinIO local object storage performs write/read/restart
  durability for platform object paths.
- Acceptance criteria:
  - Existing round-trip validator is mapped in Step 6b output index as a
    behavior test.
  - Runtime lane runs the validator and preserves artifacts.
  - If tests are ALL_GREEN on HEAD, accept and promote VERIFIED because
    the behavior is externally observable and implementation-independent.
- Fixture source: object payload fixture and bucket fixture.
- Anti-scope: no real Vultr Object Storage apply.

### SLICE-R.09 — INIT-105 TLS/DNS recovery

- Owner agent: behavior-investigator, test-writer for output index and
  gaps, code agent if needed.
- Dependencies: SLICE-R.03.
- Contract: local certificate issuance and in-cluster DNS resolution work
  for the sample hostname.
- Acceptance criteria:
  - Runtime proof waits for cert-manager, step-ca, sample Certificate
    Ready, and in-cluster DNS resolution.
  - Test intent is mapped to proposal exit criteria, not chart/version
    literals.
  - Green proof runs in cluster-equipped CI.
- Fixture source: hostname and Certificate fixtures.
- Anti-scope: no production ACME or Cloudflare mutation.

### SLICE-R.10 — INIT-106 Crossplane app-cluster recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.01, SLICE-R.03.
- Contract: Crossplane core/provider is healthy, `AppCluster` claim
  reaches Ready, and handoff connection contract is published.
- Acceptance criteria:
  - The current webhook bug no longer blocks admission.
  - AppCluster claim runtime validator is CI-visible.
  - If independent tests expose the prior sequencing fix as relied-upon
    behavior, a narrow RCA artifact is required before code changes.
  - Deletion-safety remains a named residual unless included in the
    contract generated by Step 6a.
- Fixture source: AppCluster claim fixture and connection-secret fixture.
- Anti-scope: no broad Crossplane composition redesign.

### SLICE-R.11 — INIT-107 cluster security recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.03.
- Contract: PSS, NetworkPolicy denial, and RBAC denial hold while
  required platform communication is still allowed.
- Acceptance criteria:
  - Privileged Pod apply is rejected.
  - Unauthorized network probe to protected service is denied.
  - Unauthorized namespace creation returns `no`.
  - Crossplane webhook reachability from SLICE-R.01 remains green to
    prevent observability-only policy regression.
- Fixture source: denied Pod, network probe, RBAC subject fixtures.
- Anti-scope: no auth-stack policy behavior.

### SLICE-R.12 — INIT-108 registry recovery

- Owner agent: behavior-investigator, test-writer/gates, code agent if
  needed.
- Dependencies: SLICE-R.03.
- Contract: local image build, push, pull, and pod execution works for a
  sample container.
- Acceptance criteria:
  - Runtime validator builds the sample image, pushes to local registry,
    runs a Pod, and asserts behavior from logs.
  - CI lane builds and preserves logs/artifacts.
  - Registry layout assertions are contract-derived, not copied from
    implementation.
- Fixture source: sample Containerfile and image metadata fixture.
- Anti-scope: no production registry.

### SLICE-R.13 — INIT-109 Buildkite recovery

- Owner agent: behavior-investigator, test-writer, red/green gates, code
  agent if needed.
- Dependencies: SLICE-R.02.
- Contract: local pipeline runner supports the declared command/wait
  surface and real-mode agent setup is explicit and token-safe.
- Acceptance criteria:
  - Unit/component tests validate supported step behavior, unknown step
    failure, unsupported type failure, dry-run no-command semantics, and
    artifact behavior without snapshotting the exact full step list.
  - Infisical token flow test proves token material is not committed.
  - Static/channel literal assertions are rewritten or removed.
  - HARMFUL test-level finding is closed.
- Fixture source: pipeline YAML fixture set and token-path fixture.
- Anti-scope: no Buildkite SaaS account provisioning.

### SLICE-R.14 — INIT-110 Kong ingress recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.09, SLICE-R.12.
- Contract: Kong route, DNS, certificate, and backend health work for the
  local sample service.
- Acceptance criteria:
  - Runtime proof curls MinIO health through Kong over the intended host.
  - Chart/version literals are no longer treated as behavioral proof.
  - Known prior ingress issuer/class bug-shaped fixes are backed by RCA
    notes if recovery depends on them.
- Fixture source: host route fixture, Certificate fixture, backend health
  fixture.
- Anti-scope: no auth, rate limiting, Kong Manager, or production ACME.

### SLICE-R.15 — INIT-111 data-plane recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.08, SLICE-R.13.
- Contract: CNPG cluster is Ready, Atlas migration is Ready, and `psql`
  verifies the schema/data path.
- Acceptance criteria:
  - Runtime mode is CI-visible and not masked by static-only success.
  - Backup object-store configuration is asserted only as precondition
    for INIT-112, not as restore proof.
  - Prior runtime-policy/storage-project fixes get RCA notes if relied
    on.
- Fixture source: migration SQL fixture, DB credentials fixture, psql
  proof fixture.
- Anti-scope: no backup scheduling or restore drill in this slice.

### SLICE-R.16 — INIT-112 backup/DR recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.15.
- Contract: scheduled backup exists and a deterministic manual backup can
  restore known data into a fresh CNPG cluster.
- Acceptance criteria:
  - Tests verify backup object creation and restore data equality.
  - Static scheduled-backup assertions are insufficient unless paired
    with runtime restore proof.
  - If restore semantics are absent from available proposal text, the
    slice escalates before Step 6b writes guessed tests.
- Fixture source: seed SQL fixture, manual Backup fixture, restore-cluster
  fixture.
- Anti-scope: no application-level backups, no production DR.

### SLICE-R.17 — INIT-113 application workloads recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.12, SLICE-R.14, SLICE-R.15.
- Contract: API and Discord workloads start with Infisical-managed
  secrets, migrated database, MinIO bucket bootstrap, and Kong ingress.
- Acceptance criteria:
  - Runtime proof checks API Ready, DB connected/migrated, Kong ingress,
    and Discord pod presence.
  - Image tags are fixture inputs, not behavioral assertions.
  - Service tests wired in SLICE-R.02 remain green or documented with
    residuals.
- Fixture source: app image fixture, DB seed fixture, ingress fixture,
  API/Discord runtime fixture.
- Anti-scope: no auth or tenant policy.

### SLICE-R.18 — INIT-114 auth stack DECOMPOSE rebuild

- Owner agent: orchestrator for new contract; behavior-investigator for
  ambiguous intent; test-writer; red-phase-gate; code agent; green-phase-
  gate; process-tree-auditor.
- Dependencies: SLICE-R.14, SLICE-R.17.
- Contract: OIDC/Auth stack, Pomerium protected routing, and Cedar
  authorization decisions are specified before tests and implementation.
- Acceptance criteria:
  - Step 6a defines OIDC flow, Pomerium routing, protected API headers,
    Cedar allow/deny/outage behavior, and fixture application points.
  - Step 6b authors tests without reading current implementation.
  - Tests cover 401 missing identity, 403 Cedar deny, 503 Cedar
    unavailable, and authorized protected proof.
  - Existing implementation may survive only if independent tests pass
    against it and green-phase/process-tree evidence is valid.
  - Step 6c product-code diff is structurally locked to at most 200
    changed lines and at most 5 files; process-tree-auditor verifies the
    bound, and any excess escalates to a separate proposal. Addresses
    SCOPE-B3.
- Fixture source: OIDC identity fixture, Pomerium header fixture, Cedar
  decision matrix fixture, Playwright auth fixture.
- Anti-scope: no production OIDC federation, no tenant isolation.

### SLICE-R.19 — INIT-115 access-policy DECOMPOSE rebuild

- Owner agent: orchestrator, behavior-investigator, test-writer, gates,
  code agent, process-tree-auditor.
- Dependencies: SLICE-R.18 for protected auth path where needed.
- Contract: Cedar Allow/Deny matrix for principal x resource x action is
  canonical and test-authored before any policy implementation changes.
- Acceptance criteria:
  - Contract includes user, Buildkite service, Crossplane provider, and
    denied principal cases named in the original proposal.
  - Tests assert decisions from the matrix, not policy-id literals.
  - Break-glass/rotation behavior is tested only where contract text
    explicitly pins it; otherwise residual is recorded.
  - Existing validator literals are rewritten or deleted.
  - Step 6c product-code diff is structurally locked to at most 200
    changed lines and at most 5 files; process-tree-auditor verifies the
    bound, and any excess escalates to a separate proposal. Addresses
    SCOPE-B3.
- Fixture source: Cedar matrix fixture and bundle-load fixture.
- Anti-scope: no tenant-specific dimensions.

### SLICE-R.20 — INIT-116 tenant-isolation DECOMPOSE rebuild

- Owner agent: orchestrator, behavior-investigator, test-writer, gates,
  code agent, process-tree-auditor.
- Dependencies: SLICE-R.19.
- Contract: same-tenant access is allowed and cross-tenant namespace,
  RBAC, NetworkPolicy, Infisical, S3, DB, and Cedar paths are denied.
- Acceptance criteria:
  - Contract defines tenant principals/resources before tests.
  - Tests include cross-tenant denial expectations.
  - Runtime proofs cover at least one Kubernetes denial and one Cedar
    denial; residuals name any untested S3/DB path.
  - The existing implementation survives only if independent tests pass
    without implementation-derived assumptions.
  - Step 6c product-code diff is structurally locked to at most 200
    changed lines and at most 5 files; process-tree-auditor verifies the
    bound, and any excess escalates to a separate proposal. Addresses
    SCOPE-B3.
- Fixture source: tenant resource fixture generated by
  `spawn_platform_channel.py --tenant`, Cedar tenant fixture.
- Anti-scope: no observability changes.

### SLICE-R.21 — INIT-117 observability recovery

- Owner agent: behavior-investigator, test-writer, gates, code agent if
  needed.
- Dependencies: SLICE-R.11 and SLICE-R.20 where tenant labels are
  referenced.
- Contract: local observability stack proves scrape targets, dashboard
  provisioning, sample alert ingestion, and sample log query.
- Acceptance criteria:
  - Runtime validator runs in cluster-equipped CI.
  - ServiceMonitor list/order snapshots are replaced with target
    behavior checks where possible.
  - The Crossplane webhook NetworkPolicy regression is guarded by
    SLICE-R.01 tests before observability policy changes are accepted.
  - Dashboard/alert semantics that are implementation-defined are sent
    back to behavior-investigator.
- Fixture source: sample alert, sample log, target query, dashboard
  fixture.
- Anti-scope: no third-party alert integrations.

### SLICE-R.22 — INIT-118 web UI DECOMPOSE rebuild

- Owner agent: orchestrator, behavior-investigator, test-writer, red/
  green gates, code agent, process-tree-auditor.
- Dependencies: SLICE-R.18 for auth path; SLICE-R.17 for app workload.
- Contract: web routing, form submit, auth-gated endpoint behavior,
  FontAwesome/Ark/TanStack integration, and local ingress reachability
  are defined before tests.
- Acceptance criteria:
  - Component tests cover form renderer and expected UI controls from
    contract, not demo heading text.
  - E2E tests cover route reachability, auth-gated API behavior, and one
    form submit path.
  - Cluster proof must not pass with no web pods or curl `000`.
  - Existing implementation may survive only under independent tests.
  - Step 6c product-code diff is structurally locked to at most 200
    changed lines and at most 5 files; process-tree-auditor verifies the
    bound, and any excess escalates to a separate proposal. Addresses
    SCOPE-B3.
- Fixture source: form schema fixture, auth identity fixture, API fixture,
  Playwright route fixture.
- Anti-scope: no INIT-120+ product UI surfaces.

### SLICE-R.23 — INIT-119 cross-cutting E2E rebuild

- Owner agent: orchestrator for aggregate contract; test-writer for E2E
  suite; red-phase-gate where Python tests exist; E2E gate for shell/
  Playwright evidence; code agent only after tests; green-phase-gate
  where applicable; process-tree-auditor.
- Dependencies: SLICE-R.05..R.22 contracts.
- Contract: rebuild the 19 cross-cutting tests from per-layer contracts
  while preserving `run-fullstack.sh`, `infra/tests/e2e/lib/`,
  Playwright harness, and Buildkite pipeline architecture.
- Acceptance criteria:
  - The 19 test files are not copied from the WIP same-run suite as
    canonical contract; they are regenerated from per-layer contracts.
  - Each test maps to a Step 6b output-index item and fixture source.
  - `run-fullstack.sh` passes against a clean local cluster.
  - `docs/infra-e2e-status.md` records honest pass/fail status from the
    run, not a stale generated artifact.
  - Browser-dependent flows fail or block visibly when the browser path
    is unavailable.
  - Step 6c product-code diff is structurally locked to at most 200
    changed lines and at most 5 files; process-tree-auditor verifies the
    bound, and any excess escalates to a separate proposal. Addresses
    SCOPE-B3.
- Fixture source: `infra/tests/e2e/lib/`, Playwright fixtures, per-layer
  contract fixtures.
- Anti-scope: no remote full-stack deployment.

### SLICE-R.24 — Blocking workflow evidence gates in Buildkite

- Owner agent: orchestrator; code agent for Buildkite integration;
  process-tree-auditor for expected process; coverage-auditor for
  before/after.
- Dependencies: at least SLICE-R.02; can run in parallel with later
  layer recovery because the model gate commands remain advisory while
  the Buildkite wrapper is blocking.
- Contract: `red-phase-gate`, `green-phase-gate`, and
  `process-tree-auditor` reports are generated as Phase 6 artifacts, and
  a Buildkite verdict step enforces them with verdict-grep -> exit-code:
  missing required artifacts fail; RED-phase verdict other than
  `CONFIRMED_RED` fails test-authoring slices; GREEN-phase verdict other
  than `CONFIRMED_GREEN` fails code-fix slices; blocking process-tree
  verdicts fail the build. Addresses AUDIT-A2 and SHORTCUT-S1.
- Acceptance criteria:
  - Buildkite collects `RED_PHASE.md`, `GREEN_PHASE.md`, Step 6b output
    index, Step 6c consumption evidence, and process-tree audit report.
  - A blocking Buildkite step greps the verdict line in `RED_PHASE.md`
    and exits non-zero when a test-authoring slice is not
    `CONFIRMED_RED`.
  - A blocking Buildkite step greps the verdict line in `GREEN_PHASE.md`
    and exits non-zero when a code-fix slice is not `CONFIRMED_GREEN`.
  - The same wrapper exits non-zero for missing reports, missing Step 6b
    output index, missing Step 6c consumption evidence, `BLOCKED`
    pytest collection, or process-tree-auditor blocking verdict.
  - Artifact upload remains for diagnosis, but artifact collection is not
    the gate.
- Fixture source: scratch-dir report fixture and Buildkite artifact path
  fixture.
- Anti-scope: no replacement of the formal Phase 4/6 model gates.

### SLICE-R.25 — Legacy test modernization and migration

- Owner agent: behavior-investigator for legacy intent; test-writer for
  modernization tests; code agent only for migration/deletion mechanics;
  coverage-auditor; process-tree-auditor.
- Dependencies: SLICE-R.02 for CI service-suite wiring and SLICE-R.04
  for captured contract-test rewrite rules.
- Contract: legacy tests at repo-root `tests/`, `services/api/tests/`,
  and `services/discord/tests/` are audited against current Phase 6
  patterns, classified, modernized or migrated where needed, and wired
  into CI when they survive. Addresses AUDIT-A3.
- Acceptance criteria:
  - Every legacy test file in repo-root `tests/`, `services/api/tests/`,
    and `services/discord/tests/` receives exactly one classification:
    KEEP_AS_IS, MODERNIZE, MIGRATE, or DELETE_AND_REWRITE.
  - KEEP_AS_IS files name the current contract they verify and the CI
    step that runs them.
  - MODERNIZE files are updated in place to remove captured/structural
    assertions and follow current fixture patterns.
  - MIGRATE files move to the service-owned test directory that owns the
    behavior, with old paths deleted rather than aliased.
  - DELETE_AND_REWRITE files are removed only after replacement tests or
    residual-risk disposition exists.
  - All surviving tests are wired into `.buildkite/pipeline.yml` or the
    relevant service lane.
- Fixture source: existing service conftest modules, Discord fake client
  fixtures, API testcontainers fixtures, and legacy root test files.
- Anti-scope: no new daemon feature work and no treating legacy root
  tests as service proof before classification.

## Local-as-first-deployment proof (per slice and aggregate)

- Per-slice proof rule: every Phase 6 slice must record red-phase-gate
  verdict before Step 6c consumes tests, then green-phase-gate after
  Step 6c. CONFIRMED_RED is expected for new behavior. MIXED is accepted
  when some tests legitimately encode already-correct behavior and some
  expose missing behavior. ALL_GREEN is suspicious by default and must be
  routed back through behavior-investigator unless the intended behavior
  was already correctly implemented and the tests are implementation-
  independent. For SLICE-R.24 Buildkite enforcement, test-authoring
  slices are stricter: RED-phase verdict must be `CONFIRMED_RED` or the
  blocking wrapper fails. Addresses AUDIT-A2 and SHORTCUT-S1.

- Per-slice process proof: process-tree-auditor must verify the Step 6b
  and Step 6c invocations are separate, Step 6b output index exists,
  Step 6c logs consumed that index and test paths before code changes,
  and downstream CodeRabbit did not start before Phase 6 proof existed.

- SLICE-R.01 aggregate contribution: Crossplane webhook admission dry-run
  succeeds and the webhook endpoint is reachable under the intended
  NetworkPolicy posture.

- SLICE-R.02 aggregate contribution: service suites are visible in
  mainline CI, with API DEAD/VERIFIED tests promoted operationally.

- SLICE-R.03 aggregate contribution: cluster-equipped runtime validators
  run as a real lane, not static-only substitutes.

- SLICE-R.04 aggregate contribution: captured contract tests are either
  rewritten as proposal-derived behavior tests or removed with explicit
  coverage/residual disposition.

- SLICE-R.05..R.17 aggregate contribution: CONTINUE layers gain
  independent recovery tests and red/green/process evidence while
  preserving implementation only where tests confirm it.

- SLICE-R.18..R.23 aggregate contribution: DECOMPOSE layers rebuild
  contract, tests, and implementation order so security, policy, tenant,
  web, and E2E validation are not self-authored mirrors.

- SLICE-R.24 aggregate contribution: future Phase 6 evidence appears in
  Buildkite artifacts and fails the build when required verdicts or
  process evidence are missing or non-confirming. Addresses AUDIT-A2 and
  SHORTCUT-S1.

- SLICE-R.25 aggregate contribution: legacy root and service test files
  are classified, modernized or migrated where needed, and wired into CI
  when they survive. Addresses AUDIT-A3.

- Aggregate proof: after slice recovery, run
  `infra/tests/e2e/run-fullstack.sh` against a clean local cluster. All
  19+ cross-cutting tests must pass with VERIFIED contracts. Any skip or
  block must name the missing supported path and either stop the merge or
  appear in `risk/NN-test-residuals.md` with a net-value statement.

## Risk and supported-surface track

- Current-state risk reduced: false confidence from CAPTURED tests;
  bring-up blocked by Crossplane webhook isolation; 31% of test files not
  run at all; 19 INITs with broken Phase 6 firstness evidence; security
  and policy surfaces relying on literal resolver assertions.

- Blast radius added: time investment; CI lane changes; churn on
  per-INIT validators; deletion or rewrite of captured tests; possible
  code changes where independent tests expose real mismatches; more
  Buildkite runtime cost for cluster-equipped validation.

- Supported surface: local-first deployment substrate and local CI proof.
  The recovery does not claim production readiness, remote Vultr apply,
  Discord-visible mutation, or user-facing release readiness. Existing
  remote plan-only lanes, if any, are unchanged; this recovery does not
  add or remove them.

- Migration path: in place, one slice at a time. No parallel validator
  track becomes canonical. Rewritten tests replace captured tests when
  they cover the same behavior. Runtime lanes augment static lanes only
  where static checks remain meaningful. Legacy tests migrate only after
  SLICE-R.25 classification and without compatibility aliases.

- Rollback path: every slice is reversible by git revert. CI lane changes
  can be reverted independently from product-code changes because the
  slice order separates wiring, runtime validation, and layer behavior.

- Observability: each slice emits red-phase report, green-phase report,
  Step 6b output index, Step 6c consumption log, process-tree audit, and
  coverage-auditor before/after where test classification changes. The
  aggregate run emits E2E artifacts and `docs/infra-e2e-status.md`.
  SLICE-R.24 additionally emits the Buildkite verdict-grep output and
  exit code used for the blocking gate.

- Net value: positive if the recovery converts dead verified tests into
  CI-gated evidence, rewrites captured security/policy/web tests from
  contracts, and removes the Crossplane webhook blocker without
  broadening unrelated network access. Negative-value trigger: Phase 4
  supported-surface risk finds that local-first validation is no longer
  the supported deployment target or that CI cost prevents routine use.

## Anti-scope

- Adding new product features.
- Real Vultr deployment or production remote apply.
- INIT-120+ product UI surfaces.
- Discord-visible writes or guild mutations.
- New hosting decisions.
- Backwards-compatibility shims for old validator behavior.
- Parallel old/new validator tracks.
- Re-authoring working implementation where independent tests already
  verify the intended contract.
- Treating legacy root daemon tests as product-service proof.
- Discarding legacy root daemon tests without SLICE-R.25 classification.
- Promoting captured tests to VERIFIED solely because they now run in CI.

## Assumption register

| ID | Assumption | Evidence | Invalidated by | Consequence |
|---|---|---|---|---|
| A1 | The operator-webhook RCA hypothesis is correct: INIT-117 NetworkPolicy isolates webhook ingress in Crossplane and same-pattern operator namespaces. | `research/01-rca-crossplane-webhook-unreachable.md` shows ready pod/service/listener plus kube-router reject rules and names CNPG/cert-manager as same-shape surfaces. | SLICE-R.01 tests-first reachability still fails after removing or correcting policy isolation, revealing a different failure mode. | Stop SLICE-R.01 and return to RCA before code changes. Addresses SUPPORTED-SURFACE-1. |
| A2 | Behavior-investigator can derive intended behavior for INIT-101..117 from original proposals, commits, and product goals. | Existing `plans/proposals/` and `plans/research/` artifacts cover the INIT layers. | A layer's proposal is too vague to produce testable contract without implementation archaeology. | Escalate to user at the human-gated boundary; do not let Step 6b guess. |
| A3 | DECOMPOSE layers INIT-114/115/116/118/119 can recover via test-first authorship without full rewrite. | Process audit says implementation may survive as candidate but provenance is untrusted. | Independent tests reveal implementation contract is fundamentally wrong beyond minor 6c repair. | Split the layer into smaller Phase 6 slices or revise proposal after risk gate. |
| A4 | `services/api/tests/**` are high-quality enough to promote operationally once CI runs them. | Coverage audit classifies most API files as DEAD/VERIFIED with real Postgres/httpx behavior. | CI wiring exposes suite-wide fixture brittleness that prevents routine execution or tests depend on hidden local state. | Treat as implementation bug in SLICE-R.02 or record residual; do not count as VERIFIED until green. |
| A5 | Runtime validators L04-L08 can run on a cluster-equipped CI lane with PR-gated execution for cluster-dependent Phase 6 recovery slices and nightly scheduled execution for aggregate coverage. | Validators already exist and the E2E pipeline has a 180-minute cluster lane; R1 supported-surface gate resolved cadence as PR-gated plus nightly. | Buildkite resource limits, cluster flakiness, or missing credentials prevent routine execution of the lane itself. | Blocking signal: return to supported-surface/deployment research; residuals may cover bounded validator paths, not absence of the runtime lane. Addresses AUDIT-A1 and SUPPORTED-SURFACE-2. |
| A6 | Advisory model gate reports can remain advisory only when Buildkite wraps them with blocking verdict-grep steps. | `red-phase-gate` and `green-phase-gate` are explicitly advisory, process-tree-auditor produces reports, and SLICE-R.24 defines the Buildkite exit-code wrapper. | Buildkite permits missing reports, non-confirming verdicts, or blocking process-tree findings to pass. | Treat as SLICE-R.24 failure and re-run shortcut/audit risk after correction. Addresses AUDIT-A2 and SHORTCUT-S1. |
| A7 | Local-first is still the correct supported surface for recovery. | Phase 5 completion docs and audit target local bring-up; real Vultr is out of scope. | User or DECISIONS.md changes the deployment target before Phase 6 starts. | Return to Phase 2.5 problem map and supported-surface risk. |
| A8 | Existing E2E harness architecture is reusable even though test files are not canonical. | Audit excludes framework files from test count and calls `run-fullstack.sh`, `lib/`, Playwright, and Buildkite pipeline architecture reusable. | Hookpoint research finds harness behavior encodes broken WIP assumptions. | Decompose SLICE-R.23 further and replace the affected harness component. |

## Resolved Phase 4 risk gate decisions

- Does supported-surface risk agree that local-first recovery has
  positive value without real Vultr deployment? Yes; TerminationSignal
  NONE and LOW supported-surface verdict.
- Does audit risk accept the decomposition? R1 required explicit CI lane
  naming, blocking Buildkite wrappers, and legacy test modernization;
  those are now bound to SLICE-R.03, SLICE-R.24, and SLICE-R.25.
  Addresses AUDIT-A1, AUDIT-A2, and AUDIT-A3.
- Does shortcut risk accept advisory Buildkite gates? No; SLICE-R.24 now
  requires blocking verdict-grep -> exit-code wrappers while preserving
  advisory model gate semantics. Addresses SHORTCUT-S1.
- Does scope risk require a structural lock for DECOMPOSE slices? Yes;
  SLICE-R.18/R.19/R.20/R.22/R.23 now cap Step 6c product-code diffs at
  200 changed lines and 5 files, verified by process-tree-auditor.
  Addresses SCOPE-B3.
- Does supported-surface risk require a cluster-lane cadence? Yes;
  cluster-runtime Phase 6 recovery slices are PR-gated, while unrelated
  slices use scheduled/manual runs and nightly aggregate coverage.
  Addresses SUPPORTED-SURFACE-2.

## Phase 5 hookpoint handoff

- Map `.buildkite/pipeline.yml` and `.buildkite/e2e-fullstack.yml`
  commands to the service suites and runtime validators.
- Map `.buildkite/pipeline-cluster.yml` or the equivalent
  `.buildkite/pipeline.yml` conditional step, plus
  `.buildkite/pipeline-nightly.yml` or scheduled trigger. Addresses
  AUDIT-A1.
- Map SLICE-R.24 verdict-grep inputs, expected verdict lines, and
  non-zero exit cases for red, green, missing artifacts, and blocking
  process-tree reports. Addresses AUDIT-A2 and SHORTCUT-S1.
- Map each captured `infra/tests/test_*_contract.py` assertion to either
  a proposal-derived behavior, a structural check, or deletion.
- Map runtime validators to cluster fixture requirements and artifact
  outputs.
- Map Crossplane, CNPG, cert-manager, and any other matching
  operator-webhook NetworkPolicy manifests, rendered webhook Services,
  webhook configurations, and admission dry-run commands for SLICE-R.01.
  Addresses SUPPORTED-SURFACE-1.
- Map service test dependencies for `services/api`, `services/discord`,
  and `services/web`.
- Map legacy test files under repo-root `tests/`, `services/api/tests/`,
  and `services/discord/tests/` to KEEP_AS_IS / MODERNIZE / MIGRATE /
  DELETE_AND_REWRITE disposition. Addresses AUDIT-A3.
- Map E2E framework files that survive INIT-119 rebuild:
  `infra/tests/e2e/run-fullstack.sh`, `infra/tests/e2e/lib/`,
  `infra/tests/e2e/lib/playwright/`, and `.buildkite/e2e-fullstack.yml`.

## Required artifacts per slice

- Step 6a contract artifact with behavior, assumptions, selected test
  level, fixture source, and acceptance criteria.
- Step 6b prompt and log.
- Step 6b output index at `${scratch_dir}/phase6/step6b-output-index.md`.
- Test files or validator files listed by exact path.
- `risk/NN-test-residuals.md` when any named risk is not verified.
- RED_PHASE report or documented non-pytest equivalent for shell/E2E
  slices.
- Step 6c prompt and log listing consumed Step 6b index and test paths.
- GREEN_PHASE report or documented non-pytest equivalent.
- Phase 6 process-tree audit report.
- Buildkite verdict-grep output and exit code for SLICE-R.24-enforced
  branches. Addresses AUDIT-A2 and SHORTCUT-S1.
- coverage-auditor before/after report when classification changes.

## Acceptance summary

- Operator-webhook NetworkPolicy reachability is repaired through a
  proper Phase 6 cycle for Crossplane, CNPG, cert-manager, and any other
  same-pattern namespace, so local app-cluster and data-plane admission
  are not blocked. Addresses SUPPORTED-SURFACE-1.
- `services/api/tests/`, `services/discord/tests/`, and `services/web`
  test commands are represented in `.buildkite/pipeline.yml`.
- Runtime validators that prove behavior run on a PR-gated
  cluster-equipped lane when their Phase 6 slice depends on cluster
  runtime, plus nightly scheduled aggregate coverage. The lane itself is
  required; only bounded validator paths may carry residual risk.
  Addresses AUDIT-A1 and SUPPORTED-SURFACE-2.
- CONTINUE layers INIT-101..113 and INIT-117 have independent
  behavior-investigation, test-writing, red/green, and process-tree
  evidence.
- DECOMPOSE layers INIT-114, INIT-115, INIT-116, INIT-118, and INIT-119
  have contract-first rebuilds with Step 6c product-code diffs capped at
  200 changed lines and 5 files unless escalated to a separate proposal.
  Addresses SCOPE-B3.
- Cross-cutting E2E tests under `infra/tests/e2e/` are rebuilt from
  per-layer contracts while preserving the harness architecture.
- Buildkite blocking verdict wrappers fail missing or non-confirming
  red/green/process evidence before merge. Addresses AUDIT-A2 and
  SHORTCUT-S1.
- Legacy tests under repo-root `tests/`, `services/api/tests/`, and
  `services/discord/tests/` are classified, modernized/migrated/deleted
  and rewritten as needed, and all surviving tests are CI-wired.
  Addresses AUDIT-A3.
