# Coverage + test-quality audit — INIT-100..118

Branch audited: `recovery/test-first-audit` @ HEAD `9b8f0b0`
Scope: every test file in the repo (Phase 5 INIT-100..119 substrate, plus
the surviving services/api, services/discord, services/web, and root
`tests/` daemon suites).
Method: per-file read, commit-provenance check (`git log --diff-filter=A`
per file), CI-alignment check against `.buildkite/pipeline.yml` and
`.buildkite/e2e-fullstack.yml`, taxonomy from
`~/ai/agents/coverage-auditor.md`.

## Headline

| Classification     | Count | % of suite |
|--------------------|------:|-----------:|
| VERIFIED_BEHAVIOR  |    27 |       19%  |
| CAPTURED_BEHAVIOR  |    52 |       37%  |
| STRUCTURAL         |    16 |       11%  |
| DEAD               |    44 |       31%  |
| HARMFUL            |     2 |        1%  |
| **TOTAL**          | **141** |    100% |

(Counts use the file's *primary* verdict. Many files are mixed; the
file-by-file table below records the secondary classification when
relevant. "DEAD" here means "exists but no CI workflow on this branch
runs it". Files that are also CAPTURED in their substance are tagged
`DEAD/CAPTURED` etc. to prevent the dead-status from masking the
quality finding.)

The headline confirms the user's suspicion. Phase 5's per-INIT layer
(L01-L18) is dominated by CAPTURED-style validators — same-commit-as-impl
authorship, literal-string assertions against pinned channel-resolver
output, no externally-derived expected values. The legitimate
behavioural test work in the repo is concentrated in
`services/api/tests/` (Phase 4 SLICE-006..024) — which, ironically, the
current Buildkite pipeline does NOT run. The runtime-mode validators
that *would* verify behaviour (object-storage round-trip, NetworkPolicy
deny, psql connect, sample-alert push) are similarly orphaned: only the
`--static-only` mode is invoked in CI.

## CI alignment summary (load-bearing)

`.buildkite/pipeline.yml` runs:

1. `python -m pytest tests infra/tests` — collects 13 contract
   pytests under `infra/tests/test_*.py` plus 7 daemon tests under
   `tests/test_*.py`.
2. Static-only validators for INIT-111, 113, 114, 115, 116, 117, 118
   (7 of the 16 shell validators).
3. Image build/push steps. No assertions.

`.buildkite/e2e-fullstack.yml` is a separate pipeline that runs the
INIT-119 cross-cutting suite. It is not invoked by `pipeline.yml`,
requires a 180-minute cluster bring-up, and at HEAD is a
`WIP: INIT-119 partial` commit. Treat it as not-on-mainline.

NOT invoked by either pipeline:

- `infra/tests/validate_platform_bootstrap.sh` (4398 lines)
- `infra/tests/validate_app_clusters_local.sh`
- `infra/tests/validate_cluster_security_local.sh`
- `infra/tests/validate_container_delivery_local.sh`
- `infra/tests/validate_object_storage_local.sh`
- `infra/tests/validate_tls_dns_local.sh`
- `infra/tests/validate_kong_ingress_local.sh`
- `infra/tests/validate_buildkite_cicd_local.sh`
- `services/api/tests/**` (68 files)
- `services/discord/tests/**` (17 files)
- `services/web/tests/compat.spec.ts`

`pytest tests infra/tests` does not recurse into `services/`, so even
the high-quality FastAPI integration tests are operationally orphaned.
There is no `services/api/pyproject.toml`-driven step in either
pipeline.

## Per-layer breakdown

Counts per layer use a file's *primary* classification. Cells with `0`
mean no test of that classification exists at that layer. "Layer total"
is the union of: shell validator(s) for that INIT, the matching
contract pytest if any, and the matching INIT-119 e2e flow.

| Layer | Total | VERIFIED | CAPTURED | STRUCTURAL | DEAD | HARMFUL |
|---|---:|---:|---:|---:|---:|---:|
| L01 cluster (INIT-101)            |  3 | 0 | 1 | 0 | 2 | 0 |
| L02 gitops (INIT-102)             |  1 | 1 | 0 | 0 | 0 | 0 |
| L03 infisical (INIT-103)          |  1 | 1 | 0 | 0 | 0 | 0 |
| L04 object storage (INIT-104)     |  2 | 0 | 0 | 0 | 2 | 0 |
| L05 tls/dns (INIT-105)            |  2 | 0 | 0 | 0 | 2 | 0 |
| L06 app cluster (INIT-106)        |  2 | 0 | 0 | 0 | 2 | 0 |
| L07 cluster security (INIT-107)   |  2 | 0 | 0 | 0 | 2 | 0 |
| L08 image registry (INIT-108)     |  2 | 0 | 0 | 0 | 2 | 0 |
| L09 buildkite (INIT-109)          |  3 | 0 | 1 | 0 | 2 | 0 |
| L10 kong ingress (INIT-110)       |  3 | 0 | 1 | 0 | 2 | 0 |
| L11 data plane (INIT-111)         |  2 | 0 | 1 | 0 | 1 | 0 |
| L12 backup/dr (INIT-112)          |  3 | 0 | 2 | 0 | 1 | 0 |
| L13 app workloads (INIT-113)      |  3 | 0 | 2 | 0 | 1 | 0 |
| L14 auth stack (INIT-114)         |  3 | 0 | 2 | 0 | 1 | 0 |
| L15 access policy (INIT-115)      |  3 | 0 | 2 | 0 | 1 | 0 |
| L16 tenant isolation (INIT-116)   |  3 | 0 | 2 | 0 | 1 | 0 |
| L17 observability (INIT-117)      |  3 | 0 | 2 | 0 | 1 | 0 |
| L18 web ui (INIT-118)             |  4 | 0 | 2 | 0 | 2 | 0 |
| L19 cross-cutting e2e (INIT-119)  | 19 | 0 | 0 | 0 |19 | 0 |
| App: API (services/api/tests)     | 68 |25 | 6 | 4 |33 | 0 |
| App: Discord (services/discord)   | 17 | 1 | 4 | 4 | 8 | 0 |
| App: Web (services/web/tests)     |  1 | 0 | 1 | 0 | 0 | 0 |
| Daemon (root tests/)              |  7 | 0 | 5 | 1 | 0 | 1 |

(Per-layer totals double-count files that overlap multiple layers —
e.g., `validate_platform_bootstrap.sh` covers parts of L01/L02/L03 — so
the column sum exceeds the headline total. The headline 141 is the
unique-file count.)

## File-by-file classification

### L01 cluster substrate (INIT-101)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_platform_bootstrap.sh` (4398 LOC) | **DEAD/CAPTURED** | Added in `8e3aa28` Phase-1 platform bootstrap, retained as overlay through INIT-101..103. NOT invoked by `.buildkite/pipeline.yml` or `e2e-fullstack.yml`. Assertions are file-existence (`assert_file_exists`), literal-string presence (`grep -q 'projectSlug: platform-storage'`), and exact-equality JSON comparisons against the resolver (e.g. lines 250-263 assert the local channel `gitops` block equals a 12-key dict copied from the implementation). The `--cluster` mode adds runtime checks but is never invoked anywhere in the repo. |
| `infra/tests/e2e/tests/01-cluster-up.sh` | **DEAD** | Added `9b8f0b0` (WIP). Does verify observable behaviour (node count from contract, `kubectl wait` Ready, in-cluster nslookup) — would be VERIFIED if the e2e pipeline ran on mainline. Currently it does not. |

### L02 gitops (INIT-102)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/e2e/tests/02-flux-reconciles.sh` | **DEAD/VERIFIED** | Real runtime behaviour: `GitRepository/humility-local Ready`, `Kustomization/humility-local Ready`, snapshot marker source_sha non-empty. The assertions are externally observable (Flux reconciled the rendered output). DEAD because the e2e pipeline is not on mainline. |

(L02 has no dedicated `validate_gitops_local.sh`. SOPS+Flux assertions
are buried inside `validate_platform_bootstrap.sh`.)

### L03 infisical (INIT-103)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/e2e/tests/04-infisical-runtime.sh` | **DEAD/VERIFIED** | Asserts the Infisical Operator deployment is Available, the bootstrap `InfisicalSecret` reaches `ReadyToSyncSecrets`, and the resulting `Secret` has non-empty data — observable runtime contract. DEAD via not-on-mainline e2e. |

### L04 object storage (INIT-104)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_object_storage_local.sh` | **DEAD/VERIFIED** | Added in `dd4d5c4` SLICE-104.07. Does a real S3 round-trip via `mc`, restarts the MinIO Pod, downloads again, and `cmp -s` the bodies — that is a genuine durability behaviour test. Has no `--static-only` mode and is not invoked by `pipeline.yml`. Effectively dead in CI. |
| `infra/tests/e2e/tests/05-storage.sh` | **DEAD** | Eight-line wrapper that delegates to the validator above. Inherits its quality. |

### L05 tls/dns (INIT-105)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_tls_dns_local.sh` | **DEAD/VERIFIED** | Added in `c376a83` SLICE-105.06. Pure runtime: cert-manager Available, step-ca StatefulSet Ready, `Certificate/humility-local-sample` Ready=True, in-cluster `nslookup minio.minio-system.humility.local` resolves. Externally observable. Not invoked by `pipeline.yml` (no `--static-only`). |
| `infra/tests/e2e/tests/06-tls-dns.sh` | **DEAD** | 21-line wrapper around the validator + extra DNS proof Pod. |

### L06 app cluster (INIT-106)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_app_clusters_local.sh` | **DEAD/VERIFIED** | Added `7e47a70` SLICE-106.05. `kubectl wait` Crossplane controllers Available, Provider Healthy, AppCluster claim Ready, nested k3d cluster nodes Ready — observable behaviour. No `--static-only`, not in `pipeline.yml`. |
| `infra/tests/e2e/tests/07-app-cluster.sh` | **DEAD** | Wrapper. |

### L07 cluster security (INIT-107)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_cluster_security_local.sh` | **DEAD/VERIFIED** | Added `fc5e448` SLICE-107.06. Genuine behaviour: `kubectl apply` of a privileged Pod is rejected by PSS (verified by parsing the rejection text), unauthorised pod cannot `nc -z` MinIO on 9000 (NetworkPolicy deny), `kubectl auth can-i` returns `no` for namespace creation. These are all externally observable security properties. Not in `pipeline.yml`. |
| `infra/tests/e2e/tests/08-cluster-security.sh` | **DEAD** | Wrapper. |

### L08 image registry (INIT-108)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_container_delivery_local.sh` | **DEAD/VERIFIED** | Added `00b48b5` SLICE-108.05. Builds a real container, pushes to the local registry, runs a Pod, and checks logs contain "INIT-108 registry smoke container running". Observable end-to-end behaviour. Not in `pipeline.yml`. |
| `infra/tests/e2e/tests/09-image-registry.sh` | **DEAD** | Wrapper. |

### L09 buildkite (INIT-109)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_buildkite_cicd_local.sh` | **DEAD/CAPTURED** | Added `0a409ad` SLICE-109.06. The contract assertions (lines 161-167) are literal string equality against `cicd.provider == buildkite`, image pin `buildkite/agent:3.104.0`, etc. — copied from the channel resolver's output. The runtime portions (smoke step exec, image build, in-cluster pull proof) are observable but gated behind `STATIC_ONLY=0`. Even with `--static-only` it is NOT invoked by `pipeline.yml`. |
| `infra/tests/test_local_buildkite_pipeline.py` | **CAPTURED** (mostly) | Added `8d6ad3c` SLICE-109.03, same commit as the runner script. `test_load_pipeline_accepts_command_and_wait_steps` (lines 24-44) asserts the literal step-key list — if a step is added/removed in `pipeline.yml`, the test fails but never tells you whether the new pipeline is correct. Two boundary tests (`test_unknown_step_key_fails`, `test_unsupported_step_type_fails`) and `test_dry_run_executes_no_commands` are genuine behavioural contracts on the runner. Net: CAPTURED-leaning with two VERIFIED items. |
| `infra/tests/e2e/tests/10-buildkite.sh` | **DEAD** | Wrapper. |

### L10 kong ingress (INIT-110)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_kong_ingress_local.sh` | **DEAD/CAPTURED-mixed** | Added `a0d532b` SLICE-110.05. `assert_channel_contract` (lines 199-218) asserts literal pinned values: chart 3.2.0, `kong:3.9`, etc. The runtime portion does an in-cluster HTTPS curl through Kong and verifies the proof path — that part is VERIFIED behaviour. Static-only mode is not in `pipeline.yml`. |
| `infra/tests/test_kong_ingress_contract.py` | **CAPTURED** | Added `a0d532b` same commit as the implementation. `test_local_ingress_contract_matches_kong_render` (test name itself describes "implementation matches implementation"). Asserts the resolver returns exactly the literal dict `{"name": "minio", "namespace": "minio-system", "service_port": 9000, ...}` AND that the rendered `values.yaml` contains the same. A bug that makes both wrong consistently passes. |
| `infra/tests/e2e/tests/11-ingress.sh` | **DEAD** | Wrapper. |

### L11 data plane (INIT-111)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_data_plane_local.sh --static-only` (CI) | **CAPTURED** | Added `3035c6c` SLICE-111.05. Static portion: contract asserts literal CNPG operator version `1.29.0`, Atlas chart `0.7.28`, retention policy `7d`, MinIO endpoint URL — all copied from resolver. Static manifests checked by `grep -q '^kind: Cluster$'` etc. — file-presence-of-string checks. Runtime portion (skipped under `--static-only`) does real psql connect and schema verify, which would be VERIFIED. CI only runs the static portion. |
| `infra/tests/e2e/tests/12-data-plane.sh` | **DEAD** | Wrapper. |

### L12 backup/dr (INIT-112)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_backup_dr_local.sh` | **CAPTURED** (when run static) | Added `e63b3cb` (`feat: add init 112 backup dr`) — same commit as INIT-112 implementation. Asserts literal endpoint, bucket, retention strings. NOT invoked by `pipeline.yml`. Provided for completeness because the e2e pipeline does invoke it via `13-backup-dr.sh`. |
| `infra/tests/test_backup_dr_contract.py` | **CAPTURED** | Same commit. `test_local_backup_contract_targets_minio_bucket` asserts `channel["backup"] == { ...11 literal keys... }`. The expected dict was clearly copied from the resolver output — there is no spec/proposal that names `endpoint == "http://minio.minio-system.svc.cluster.local:9000"` as a behavioural contract; that is an implementation choice. |
| `infra/tests/e2e/tests/13-backup-dr.sh` | **DEAD** | Wrapper. |

### L13 application workloads (INIT-113)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_application_workloads_local.sh --static-only` (CI) | **CAPTURED** | Added `5aca15d` SLICE-113.x same commit as the workload manifests. Static contract: literal image tag `init-113-local`, host `api.local.humility.local`, etc. |
| `infra/tests/test_application_workloads_contract.py` | **CAPTURED** | Same commit. `test_server_manager_workloads_use_channel_registry_images` asserts exactly `"k3d-humility-local:5000/local/server-manager-api:init-113-local"`. The image string is an implementation choice; the test's name describes the assertion, not a behavioural contract. `test_runtime_secrets_are_infisical_managed` asserts the resolver returns a literal scope dict equal to the implementation's literal scope dict. |
| `infra/tests/e2e/tests/14-application-workloads.sh` | **DEAD** | Wrapper. |

### L14 auth stack (INIT-114)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_auth_stack_local.sh --static-only` (CI) | **CAPTURED** | Added across SLICE-114.05/114.07/114.09 — fix-then-test, not test-first. Static checks are literal. |
| `infra/tests/test_auth_stack_contract.py` | **CAPTURED** | Added `30acffc` SLICE-114.03 (same week as `6c2194f` SLICE-114.04 manifests). Asserts `chart_version == "2026.2.2"`, image SHA, host, namespace — copied from `auth_stack` block of resolver. The first comment line says "Exact versions are deliberate channel-contract checks, not a snapshot" which is exactly what one writes when the test feels like a snapshot. |
| `infra/tests/e2e/tests/15-auth-stack.sh` | **DEAD** | Wrapper that also runs Playwright but skips on browser unavailability. |

### L15 access policy (INIT-115)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_access_policy_local.sh --static-only` (CI) | **CAPTURED** | Added `9b292ac` (`Add INIT-115 access policy substrate` — single commit for both impl and validator). |
| `infra/tests/test_access_policy_contract.py` | **CAPTURED** | Same commit. Hardcoded policy-id sets, literal Cedar principal strings, literal cadence_days dict. Test name `test_access_policy_channel_contract` again describes "the contract is what the resolver returns", which is implementation-mirror. |
| `infra/tests/e2e/tests/16-access-policy.sh` | **DEAD** | Wrapper. |

### L16 tenant isolation (INIT-116)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_tenant_isolation_local.sh --static-only` (CI) | **CAPTURED** | Added `353576e` (`Add tenant channel isolation model`). |
| `infra/tests/test_tenant_isolation_contract.py` | **CAPTURED** | Same commit. Lines 67-80 assert `isolation == { ... 17 literal keys ... }` — the comment explicitly says "Intentionally strict: tenant_isolation additions are contract changes" which is the agent doc's #1 example of behaviour-capture (snapshot assertion without spec). |
| `infra/tests/e2e/tests/17-tenant-isolation.sh` | **DEAD** | Wrapper. |

### L17 observability (INIT-117)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_observability_local.sh --static-only` (CI) | **CAPTURED** | Added `504de05` (`Add observability scrape contracts and harness`). Static: jq assertion of literal image tags `prom/prometheus:v2.54.1`, `grafana/grafana:11.2.0`, etc. The runtime portion (Prometheus targets up, sample alert posted to Alertmanager round-trips, sample Loki log queries back) is real behaviour but gated. CI runs static. |
| `infra/tests/test_observability_contract.py` | **CAPTURED** | Same commit. `test_local_observability_channel_contract` asserts a 9-image-tag literal dict. `test_service_monitors_cover_required_platform_components` asserts `names == [12 literal strings]` — order matters because `==` is used on a list. Add or remove a ServiceMonitor in either manifest or resolver and the test breaks consistently. |
| `infra/tests/e2e/tests/18-observability.sh` | **DEAD** | Wrapper. |

### L18 web ui (INIT-118)

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/validate_web_ui_local.sh --static-only` (CI) | **CAPTURED** | Added `edc08e5` SLICE-118.10 — the *same* commit as the toolchain harness. The whole `assert_package_surface` block is copied package version pins. `assert_kustomize` greps for the literal image tag `init-118-local`. |
| `infra/tests/test_web_ui_contract.py` | **CAPTURED** | Same commit. `test_web_package_locks_solid_2_and_frontend_stack` lists 9 dependency-version equality checks. These are implementation choices, not behavioural contracts; the test answers "did somebody change package.json" not "does the web app behave correctly". |
| `infra/tests/e2e/tests/19-web-ui.sh` | **DEAD** | Wrapper that also calls Playwright `compat.spec.ts` indirectly. |
| `services/web/tests/compat.spec.ts` | **DEAD/CAPTURED** | Added `edc08e5` SLICE-118.10 same commit as web harness. Two Playwright checks: a heading text and a roving-tabindex behaviour. The roving-tabindex test would be VERIFIED behaviour. The heading test asserts the literal label "Dark Nemesis application" — copied from the demo content. No CI runs `npm test` on this branch, so DEAD overall. |

### L19 cross-cutting E2E (INIT-119)

All 19 files added in commit `9b8f0b0` (`WIP: INIT-119 partial`). The
file `docs/infra-e2e-status.md` is generated by `run-fullstack.sh` so
there is no committed evidence the suite has ever passed end-to-end.
The pipeline that runs them (`.buildkite/e2e-fullstack.yml`) is
separate from `pipeline.yml` and not on default trigger.

| File | Verdict | Evidence |
|---|---|---|
| `infra/tests/e2e/tests/01-cluster-up.sh`            | DEAD | k3d node count vs channel + Ready + in-cluster nslookup — would be VERIFIED if it ran. |
| `infra/tests/e2e/tests/02-flux-reconciles.sh`       | DEAD | GitRepository + Kustomization Ready + sentinel marker — would be VERIFIED. |
| `infra/tests/e2e/tests/03-sops-bootstrap.sh`        | DEAD | Decrypts a sentinel and asserts payload string — VERIFIED-style. |
| `infra/tests/e2e/tests/04-infisical-runtime.sh`     | DEAD | Operator + secret round-trip. |
| `infra/tests/e2e/tests/05-storage.sh`               | DEAD | Wrapper around `validate_object_storage_local.sh`. |
| `infra/tests/e2e/tests/06-tls-dns.sh`               | DEAD | Wrapper around `validate_tls_dns_local.sh` + extra DNS check. |
| `infra/tests/e2e/tests/07-app-cluster.sh`           | DEAD | Wrapper. |
| `infra/tests/e2e/tests/08-cluster-security.sh`      | DEAD | Wrapper. |
| `infra/tests/e2e/tests/09-image-registry.sh`        | DEAD | Wrapper. |
| `infra/tests/e2e/tests/10-buildkite.sh`             | DEAD | Wrapper. |
| `infra/tests/e2e/tests/11-ingress.sh`               | DEAD | Wrapper. |
| `infra/tests/e2e/tests/12-data-plane.sh`            | DEAD | Wrapper. |
| `infra/tests/e2e/tests/13-backup-dr.sh`             | DEAD | Wrapper. |
| `infra/tests/e2e/tests/14-application-workloads.sh` | DEAD | Wrapper. |
| `infra/tests/e2e/tests/15-auth-stack.sh`            | DEAD | Wrapper + Playwright (skip on missing browser). |
| `infra/tests/e2e/tests/16-access-policy.sh`         | DEAD | Wrapper. |
| `infra/tests/e2e/tests/17-tenant-isolation.sh`      | DEAD | Wrapper. |
| `infra/tests/e2e/tests/18-observability.sh`         | DEAD | Wrapper. |
| `infra/tests/e2e/tests/19-web-ui.sh`                | DEAD | Wrapper + Playwright. |

The framework files (`run-fullstack.sh`, `lib/assertions.sh`,
`lib/bringup.sh`, `lib/teardown.sh`, `lib/playwright/*`) are not test
files and are not counted in the 141. They are infrastructure for the
DEAD test files.

### App: API (services/api/tests)

`pyproject.toml` declares `pytest-asyncio`, `testcontainers[postgres]`,
and `httpx` dev-deps; the suite is designed to run with real Postgres
and is NOT covered by `pipeline.yml`'s `pytest tests infra/tests` step.
All 68 files therefore inherit a "DEAD-vs-CI" annotation. The
classifications below describe *quality* assuming the dead-vs-CI
problem is fixed by adding a step.

Most files share an identical pattern: a docstring naming the WU/AC
contract from the proposal, an `httpx.AsyncClient` against a
testcontainers Postgres, and behavioural assertions that exercise real
service code (no mocks of the service layer). That is the gold-standard
shape this audit is otherwise looking for.

| File | Verdict | Evidence |
|---|---|---|
| `test_actor_middleware.py` (in `infra/tests/`) | VERIFIED | Docstring (lines 1-17) cites SLICE-008 D1 contract; tests assert behavioural outcomes (401 on missing header, X-Correlation-Id always present, request-scope context cleared after response). |
| `test_api_readiness.py` (in `infra/tests/`) | VERIFIED | "Tests fail now and pass after the SLICE-006 code agent implements..." — explicit test-first style. Asserts 503 on stopped scheduler, `not_ready` on missing migration revision. |
| `test_api_runtime.py` (in `infra/tests/`) | VERIFIED | Same style; tests `/api/v1/health` returns `alive` with version. |
| `test_discord_runtime.py` (in `infra/tests/`) | VERIFIED | SLICE-006 PR B contract. |
| `test_authority.py` | DEAD/VERIFIED | Real Postgres, real ETag/If-Match flow on `/api/v1/authority-grants`. Docstring cites WU-014 AC1+AC2. Service functions never mocked. |
| `test_authority_enforcement.py` | DEAD/VERIFIED | Mounts test-only routes behind `RequireAuthority`, exercises full decision surface. Docstring cites WU-015A AC3 with denial-reason priority order pinned to the proposal. |
| `test_authority_foundation.py` | DEAD/VERIFIED | Substrate test for authority service. |
| `test_authority_override_audit.py` | DEAD/VERIFIED | Audit emission contract for override path. |
| `test_authority_transfer.py` | DEAD/VERIFIED | Real grant transfer + audit. |
| `test_application_boundaries.py` | DEAD/VERIFIED | Negative-path boundary contract. |
| `test_application_interviews.py` | DEAD/VERIFIED | Interview state machine. |
| `test_applications.py` | DEAD/VERIFIED | Application intake. |
| `test_archive_boundaries.py` | DEAD/VERIFIED | Archive plan/execution contract. |
| `test_audit_api.py` | DEAD/VERIFIED | Audit ingestion endpoints. |
| `test_audit_foundation.py` | DEAD/VERIFIED | Substrate. |
| `test_chapter_archive_execution.py` | DEAD/VERIFIED | Archive execution behaviour. |
| `test_chapter_archive_plan.py` | DEAD/VERIFIED | Archive plan behaviour. |
| `test_chapter_governance.py` | DEAD/VERIFIED | SLICE-023 governance lifecycle. |
| `test_chapter_lifecycle.py` | DEAD/VERIFIED | SLICE-013 lifecycle, real Postgres + governance_dsn. |
| `test_chapter_role_foundation.py` | DEAD/VERIFIED | Role substrate. |
| `test_chapter_template_foundation.py` | DEAD/VERIFIED | Template substrate. |
| `test_chapter_templates.py` | DEAD/VERIFIED | Template CRUD + ETag. |
| `test_compliance_evaluation_worker.py` | DEAD/VERIFIED | SLICE-022 worker behaviour. |
| `test_compliance_evidence.py` | DEAD/VERIFIED | Evidence storage. |
| `test_compliance_ocr_correct.py` | DEAD/VERIFIED | OCR correction flow. |
| `test_compliance_ocr_extract.py` | DEAD/VERIFIED | OCR extraction. |
| `test_compliance_review_api.py` | DEAD/VERIFIED | Review endpoint contract. |
| `test_compliance_rules.py` | DEAD/VERIFIED | Rule evaluation. |
| `test_leadership_context.py` | DEAD/VERIFIED | Leadership context substrate. |
| `test_leadership_handoff_applications.py` | DEAD/VERIFIED | SLICE-024 handoff. |
| `test_leadership_handoff_tickets.py` | DEAD/VERIFIED | SLICE-024 handoff. |
| `test_members.py` | DEAD/VERIFIED | Member endpoints. |
| `test_mutations.py` | DEAD/VERIFIED | Mutation contracts. |
| `test_notification_delivery_worker.py` | DEAD/VERIFIED | Worker behaviour. |
| `test_notification_event_contract.py` | DEAD/CAPTURED | Asserts notification event shape literal. |
| `test_notification_materialization.py` | DEAD/VERIFIED | Materialization behaviour. |
| `test_notification_rules.py` | DEAD/VERIFIED | Rules. |
| `test_operational_views.py` | DEAD/VERIFIED | SLICE-017 read-model. |
| `test_permission_drift.py` | DEAD/VERIFIED | SLICE-014 drift detection. |
| `test_permission_intents.py` | DEAD/VERIFIED | Intent + drift API. |
| `test_permission_reconciliation_api.py` | DEAD/VERIFIED | Reconciliation. |
| `test_permission_temporary_api.py` | DEAD/VERIFIED | SLICE-020 temporary lifecycle. |
| `test_permission_temporary_worker.py` | DEAD/VERIFIED | Worker. |
| `test_persistence.py` | DEAD/VERIFIED | Migration head behaviour. |
| `test_policies.py` | DEAD/VERIFIED | Policy endpoints. |
| `test_policy_foundation.py` | DEAD/VERIFIED | Substrate. |
| `test_protected_authz.py` | DEAD/VERIFIED | Pomerium claims pass-through. |
| `test_read_models.py` | DEAD/VERIFIED | Read-model behaviour. |
| `test_roster.py` | DEAD/VERIFIED | Roster. |
| `test_succession_plan.py` | DEAD/VERIFIED | Succession. |
| `test_ticket_boundaries.py` | DEAD/VERIFIED | Ticket boundary contract. |
| `test_ticket_categories.py` | DEAD/VERIFIED | Categories. |
| `test_ticket_create.py` | DEAD/VERIFIED | Ticket create. |
| `test_ticket_initial_message_events.py` | DEAD/VERIFIED | Event emission. |
| `test_ticket_messages.py` | DEAD/VERIFIED | Messages. |
| `test_ticket_sla.py` (658 LOC) | DEAD/VERIFIED | SLA computation behaviour. |
| `test_ticket_transitions.py` | DEAD/VERIFIED | Transition graph. |
| `test_trust.py` (623 LOC) | DEAD/VERIFIED | Trust model. |
| `test_trust_recompute.py` | DEAD/VERIFIED | Recompute behaviour. |
| `test_trust_signals.py` | DEAD/VERIFIED | Signal aggregation. |
| `test_web_identity.py` | DEAD/VERIFIED | Pomerium claim header pass-through (4 tests, all behavioural). |
| `test_activity_model.py` | DEAD/CAPTURED | Asserts repository row shape literal. |
| `test_scheduler_foundation.py` | DEAD/CAPTURED | Asserts scheduler lifecycle dict shape literal. |
| `test_deferred_effect_foundation.py` | DEAD/CAPTURED | Substrate dict-shape assertions. |
| `test_endpoints_chapters_stubs.py` | DEAD/CAPTURED | Asserts stub responses match implementation. |
| `test_forms.py` | DEAD/CAPTURED | Asserts form schema dict literal. |
| `test_settings.py` | DEAD/STRUCTURAL | Asserts Settings rejects missing required env vars. (References `SUPABASE_DB_URL`, `SUPABASE_SERVICE_KEY` env-var names — these are kept as variable identifiers; not Supabase usage.) |
| `test_factory.py` | DEAD/STRUCTURAL | `assert callable(create_api_app)`, `assert isinstance(app, FastAPI)`. |
| `test_conftest.py` | DEAD/STRUCTURAL | Tests the test fixtures themselves. |
| `test_harness.py` | DEAD/STRUCTURAL | Tests that the `ApiTestHarnessRead` contract describes the actual fixtures. |
| `test_contracts_base.py` | DEAD/STRUCTURAL | `assert contracts_base.__all__ == []`. |
| `test_contracts_chapter_lifecycle.py` | DEAD/CAPTURED | Asserts chapter lifecycle contract dict literal. |

### App: Discord (services/discord/tests)

`pyproject.toml` declares `pytest`, `pytest-asyncio`, `pytest-mock`,
`pytest-cov`. None of these run in `pipeline.yml`. All 17 files are
DEAD-vs-CI.

| File | Verdict | Evidence |
|---|---|---|
| `test_application_interview.py` | DEAD/VERIFIED | FakeApiClient harness, but tests handler logic against real envelope/response shapes. |
| `test_application_review.py` | DEAD/CAPTURED | FakeApiClient + literal expected response bodies copied from the implementation. |
| `test_application_submission.py` | DEAD/CAPTURED | Mock-and-verify. |
| `test_application_waitlist.py` | DEAD/CAPTURED | Mock-and-verify. |
| `test_chapter_provisioning.py` | DEAD/CAPTURED | Heavy MockGuild fixture; asserts handler called specific Discord API methods with exact args. |
| `test_onboarding.py` | DEAD/CAPTURED | Mock-and-verify pattern. |
| `test_roster_sync.py` | DEAD/CAPTURED | Mock guild, assert calls. |
| `test_tickets.py` | DEAD/CAPTURED | Mock pattern. |
| `test_notifications.py` | DEAD/CAPTURED | Mock pattern. |
| `test_permission_reconciliation_adapter.py` | DEAD/CAPTURED | Mock-and-verify. |
| `test_api_context.py` | DEAD/STRUCTURAL | Context-var existence + reset behaviour. |
| `test_api_transport.py` | DEAD/STRUCTURAL | Transport request/response dataclass shape. |
| `test_interaction_framework.py` | DEAD/STRUCTURAL | Envelope construction. |
| `test_settings.py` | DEAD/STRUCTURAL | Pydantic validation behaviour. |
| `test_bot.py` | DEAD/STRUCTURAL | `test_humility_bot_is_importable_from_app_core_bot`, `test_humility_bot_enables_member_intent`, etc. — pure intent-bit and import checks. |
| `test_harness.py` | DEAD/STRUCTURAL | Fixture self-check. |
| `test_main.py` | DEAD/CAPTURED | Mock `Settings`, mock `HumilityBot`, mock `check_api_reachability`, then `assert bot.close.assert_awaited_once()`. The literal command-name list (10 entries, lines 70-81) is captured straight from the implementation's `register_interaction_handler` order. |

### App: Web (services/web/tests)

| File | Verdict | Evidence |
|---|---|---|
| `services/web/tests/compat.spec.ts` | DEAD/CAPTURED | See L18 above. |

### Daemon (root tests/)

These predate Phase 4. None run code that's still load-bearing in
the new architecture; the daemon directory is being supplanted by
`services/discord`. They DO run in `pipeline.yml` via
`pytest tests infra/tests`, so they are not DEAD-vs-CI, but they are
testing legacy code.

| File | Verdict | Evidence |
|---|---|---|
| `tests/test_daemon_init.py` | STRUCTURAL | `test_daemon_package_is_importable`, `test_daemon_docstring_mentions_key_concepts_and_submodules` — asserts a docstring contains specific substrings. Pure CAPTURED structural test. |
| `tests/test_daemon_config.py` | CAPTURED | Asserts config-dict shapes copied from the implementation. |
| `tests/test_daemon_db.py` | CAPTURED | DB schema-shape assertions. |
| `tests/test_daemon_claim.py` | CAPTURED | Claim-flow heavy mocks. |
| `tests/test_daemon_applications.py` | CAPTURED | Application-flow heavy mocks. |
| `tests/test_daemon_entry.py` | CAPTURED | Entry-point dict shape. |
| `tests/test_discord_cli.py` | **HARMFUL** | Every Discord API object is a `MagicMock`/`Mock`; the tests then assert mock calls and string formatting. The tests pass against any implementation that produces the same output strings on the same mocked-input sequence. They cannot detect a real Discord API regression because they never touch the real API; they cannot detect a domain-logic bug because the domain is mocked. They do, however, lock in the implementation's exact output formatting, blocking any non-cosmetic refactor. The "test" effectively re-implements `discord_cli` in a mock harness and asserts the implementation matches the re-implementation. |

### Other (root)

| File | Verdict | Evidence |
|---|---|---|
| `tests/test_daemon_init.py` | (counted above) |
| (no other root test files) | | |

### HARMFUL list

Two files are flagged HARMFUL:

| File | Why HARMFUL |
|---|---|
| `tests/test_discord_cli.py` | Mock-everything pattern; tests assert mocks were called, not that the program does anything. Locks in implementation strings, blocks refactor, provides no real-world coverage. |
| `infra/tests/test_local_buildkite_pipeline.py::test_load_pipeline_accepts_command_and_wait_steps` | (Test-level; the file is otherwise OK.) Asserts the exact ordered list of step keys present in `pipeline.yml`. Any time a CI step is added (which is a normal change), this test fails — but passing the test does not mean the new pipeline is correct. It will be reflexively "fixed" by updating the literal list, training developers to silence it without thinking. That is the textbook captured-snapshot harm. |

(I did not promote the L01..L18 contract pytests to HARMFUL because
their primary failure mode is "does nothing useful" rather than
"actively prevents correct behaviour". They will not block correct
fixes; they just rubber-stamp current state. CAPTURED is the right
classification.)

## Recovery priority (per layer)

For each layer, given the audit findings, the recommended next step
is shown below. (Per the user's brief, no fixes are proposed — only
audit verdicts.)

| Layer | CAPTURED ratio | Recommendation |
|---|---:|---|
| L01 cluster (INIT-101)            | dominant CAPTURED + DEAD validators | **Tests-first authoring needed** — no mainline-CI test verifies the bootstrap behaviour. The 4398-line `validate_platform_bootstrap.sh` is a static-string fortress that runs nowhere. |
| L02 gitops (INIT-102)             | only DEAD-VERIFIED test exists | **Tests-first authoring needed** — no in-CI test for Flux+SOPS reconcile behaviour. |
| L03 infisical (INIT-103)          | only DEAD-VERIFIED test exists | **Tests-first authoring needed**. |
| L04 object storage (INIT-104)     | DEAD-VERIFIED runtime exists | **Acceptable as smoke; CI gating needed** — the real S3 round-trip harness is good; it just needs to be run. |
| L05 tls/dns (INIT-105)            | DEAD-VERIFIED runtime | **Acceptable as smoke; CI gating needed**. |
| L06 app cluster (INIT-106)        | DEAD-VERIFIED runtime | **Acceptable as smoke; CI gating needed**. |
| L07 cluster security (INIT-107)   | DEAD-VERIFIED runtime | **Acceptable as smoke; CI gating needed** — best-quality runtime test in the substrate. |
| L08 image registry (INIT-108)     | DEAD-VERIFIED runtime | **Acceptable as smoke; CI gating needed**. |
| L09 buildkite (INIT-109)          | dominant CAPTURED | **Behaviour investigation needed** — replace step-list snapshot with behavioural property checks (e.g. "every step has a known type"). |
| L10 kong ingress (INIT-110)       | dominant CAPTURED static | **Behaviour investigation needed** — the only runtime-VERIFIED part is a single curl, gated by `--static-only=0` which CI does not run. |
| L11 data plane (INIT-111)         | dominant CAPTURED static | **Behaviour investigation needed**. |
| L12 backup/dr (INIT-112)          | dominant CAPTURED | **Behaviour investigation needed** — no test asserts a backup actually restores. |
| L13 application workloads (INIT-113) | dominant CAPTURED | **Behaviour investigation needed**. |
| L14 auth stack (INIT-114)         | dominant CAPTURED | **Behaviour investigation needed** — Pomerium-Authentik-Cedar OAuth flow has zero in-CI behavioural coverage. |
| L15 access policy (INIT-115)      | dominant CAPTURED | **Behaviour investigation needed**. |
| L16 tenant isolation (INIT-116)   | dominant CAPTURED | **Behaviour investigation needed** — no in-CI proof that tenant A cannot read tenant B's data. |
| L17 observability (INIT-117)      | dominant CAPTURED static | **Behaviour investigation needed** — sample-alert and Loki-push runtime tests are the right shape but gated. |
| L18 web ui (INIT-118)             | dominant CAPTURED | **Behaviour investigation needed**. |
| L19 cross-cutting e2e (INIT-119)  | DEAD entirely | **Drop and rewrite** — currently a WIP single-commit scaffold that no pipeline runs. Either land it on mainline e2e cron with an honest pass-fail history, or remove it. |
| App: API                          | dominant VERIFIED | **Keep** — but immediately add a `services/api` step to `pipeline.yml`. The asset is wasted otherwise. |
| App: Discord                      | mostly CAPTURED via mocks | **Drop and rewrite for handler logic; keep for transport contracts** — the FakeApiClient pattern is fine for transport; the MockGuild assertions are mock-and-verify and should be replaced with handler-output contract tests. Also wire the suite into CI. |
| App: Web                          | only one CAPTURED test | **Tests-first authoring needed** — the SPA has effectively no automated coverage. |
| Daemon (root tests/)              | dominant CAPTURED + 1 HARMFUL | **Drop and rewrite** — daemon is being supplanted by `services/discord`; tests should follow the code. The HARMFUL `test_discord_cli.py` should be removed before its expected-strings drift any further. |

## Coverage gaps

These are areas the proposals (`plans/proposals/init-1XX-*.md`,
`plans/research/init-1XX-*.md`) name as load-bearing behaviour, where
no test of any kind exists at HEAD on this branch.

1. **End-to-end OAuth flow** (INIT-114, INIT-118). Proposal
   `plans/proposals/init-114-auth-stack.md` names "user logs into
   web UI via Authentik, gets routed to a protected admin path through
   Pomerium, request reaches API with x-pomerium-claim-* headers, Cedar
   policy evaluates and authorizes" as the central behavioural
   contract. Only `services/api/tests/test_protected_authz.py` and
   `test_web_identity.py` exercise the API end of that flow, and they
   are DEAD-vs-CI. The Playwright smoke under `e2e/lib/playwright`
   is `e2e_skip_flow`-skipped on browser unavailability, which is the
   default in any non-interactive runner.

2. **Tenant isolation negative path** (INIT-116). Proposal names
   "tenant A cannot read tenant B's S3 prefix, namespace, or DB". The
   current test `infra/tests/test_tenant_isolation_contract.py` only
   asserts the channel resolver returns the labels dict; nothing
   exercises a deny.

3. **Backup restore drill** (INIT-112). Proposal
   `plans/proposals/init-112-backup-dr.md` names RPO/RTO and an actual
   restore drill. No test restores a backup. `validate_backup_dr_local.sh`
   only asserts a `ScheduledBackup` resource exists.

4. **CNPG failover** (INIT-111). Proposal names data-plane availability
   under primary kill. `validate_data_plane_local.sh` does psql-connect
   but does not exercise failover.

5. **Crossplane app-cluster lifecycle** (INIT-106). The validator
   asserts the claim Reaches Ready. Nothing asserts deletion safety
   (deletion of the claim deletes the nested cluster cleanly without
   stranding nodes). Proposal cites that as load-bearing.

6. **Web UI components in isolation** (INIT-118). Proposal names
   "Solid 2 + TanStack + Ark UI" component-level coverage. Only one
   Playwright spec exists, asserting two visible labels. There are no
   unit tests for the FontAwesome integration, the YAML form renderer,
   or the gap components — each of which had a dedicated SLICE.

7. **GitOps reconciliation drift detection** (INIT-102). Proposal
   names "Flux re-reconciles after manual mutation, restoring the
   GitOps source-of-truth". No test exercises that.

8. **SOPS bootstrap-only boundary lint** (INIT-102, INIT-103).
   Proposal names "no plaintext secrets are committed past the
   bootstrap allowlist". The lint script exists at
   `infra/scripts/lint-sops-boundary.py`; the validator asserts
   *that the lint passes on the committed tree* (which it does because
   the impl was authored to satisfy the lint). No test exercises the
   lint detecting an actual plaintext leak.

9. **Discord interaction-to-API end-to-end** (INIT-113, services/discord).
   Mock-based handler tests cover transport; no test asserts that a
   real Discord interaction → API → DB flow works. The
   `services/api/tests/test_authority.py` test is the API half, but
   nothing connects it to a real or recorded Discord interaction.

10. **Observability scrape coverage** (INIT-117). Proposal names
    metrics from CNPG, Crossplane, Flux, Cedar, Authentik, Kong, API,
    Discord. The validator asserts the `ServiceMonitor` CRs exist;
    nothing asserts the metrics actually arrive at Prometheus. The
    runtime portion (`Prometheus has active targets`) does run a
    weaker form of this but is gated and not in CI.

## Recommendation summary

The test-first recovery has the highest leverage in three places.

**(1) Wire `services/api/tests/` into CI.** This is the single
highest-quality block of tests in the repo — 25+ behavioural
integration tests with real Postgres, no service mocks, docstrings
that cite specific WU/AC contracts. The current `pipeline.yml` runs
none of them. A one-line addition that runs `pytest services/api/tests`
in a step with the testcontainers image converts ~25 DEAD/VERIFIED
files into VERIFIED files immediately. No new tests need to be
written for this win.

**(2) For Phase 5 layers L09-L18, replace the contract pytests
(`infra/tests/test_*_contract.py`) with behaviour-investigation work.**
These eight files all share the same flaw: they assert that the
channel resolver returns the same literal dict that the implementation
produces. The only way to "fail" them is to change the implementation
without updating the test (or vice-versa) — they cannot detect that
the resolver returns wrong values because the test author and the
implementation author were the same agent. The recovery isn't to
delete them; it is to send each through the behaviour-investigator to
identify what the proposal actually says is correct, then rewrite
expected values from the proposal rather than from the resolver.

**(3) For the runtime-only validators (L04..L08), the work is
operational, not authoring.** `validate_object_storage_local.sh`,
`validate_tls_dns_local.sh`, `validate_app_clusters_local.sh`,
`validate_cluster_security_local.sh`, `validate_container_delivery_local.sh`
are genuinely good behaviour-verification harnesses that have been
written and abandoned. They need a CI lane with a cluster (the
`e2e-fullstack.yml` queue) on a default trigger, an honest pass/fail
history, and the visible-skip patterns (`e2e_skip_flow ... requires
a reachable local browser path`) treated as red signals rather than
green ones.

The dual-edged finding is that the load-bearing-rule violation the
user named is real and observable: every layer where the same agent
authored both implementation and validator (L01, L09-L18) shows
exactly the CAPTURED pattern the agent doc warns against. The layers
where authorship was split between an earlier "test-first SLICE.05"
ticket and a later "implementation SLICE.04" ticket (e.g. SLICE-110.05
vs 110.04 — but on inspection both landed within the same agent-week
in adjacent commits) show the same pattern, so the temporal split
alone did not protect the contract. The protection has to come from a
contract authored against the proposal text, not against the
implementation's behaviour, and verified by an independent reader
before the implementation lands.
