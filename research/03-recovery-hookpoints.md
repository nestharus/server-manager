# Recovery hookpoints

Branch audited: `recovery/test-first-audit`.

Scope: Phase 5 hookpoint research for `proposals/01-recovery-test-first.md`.
This maps the 25 recovery slices onto the current codebase at HEAD and names
the reusable pieces, extension points, conflicting systems, deletion
candidates, and blocking preconditions before Phase 6 implementation starts.

The main hookpoint conclusion is that the proposal is implementable without
inventing new subsystems. Most slices plug into existing validators, GitOps
manifests, Buildkite pipelines, service `conftest.py` fixtures, and E2E
harness files. The codebase conflict is not missing infrastructure; it is that
many validators are either not run, static-only in CI, implementation-mirror
tests, or legacy daemon tests that now sit outside service ownership.

## Per-slice hookpoint table

| Slice | Files added | Files modified | Files deleted | Adjacent surfaces |
|---|---|---|---|---|
| SLICE-R.01 | `infra/tests/fixtures/operator-webhooks/`, a new operator-webhook reachability validator or pytest, Step 6 artifacts under `.tmp/recovery/R.01/` | `gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml`; possibly `infra/tests/validate_cluster_security_local.sh` to keep regression proof nearby | No broad deletion; only remove an invalid observability-only policy entry if replaced by narrower allow rules in the same commit | Reuses RCA evidence, rendered Crossplane/CNPG/cert-manager manifests, kube-router behavior, and `kubectl` probe style from existing shell validators. Conflicts with namespace-wide empty-selector `allow-observability-scrape` policies. |
| SLICE-R.02 | Buildkite service-suite steps; optional CI preflight script for Docker/testcontainers; Step 6 artifacts | `.buildkite/pipeline.yml`; possibly service-local command docs in `services/api/pyproject.toml`, `services/discord/pyproject.toml`, `services/web/package.json` only if commands are wrong | None, except do not keep obsolete CI aliases if a step is renamed | Reuses `services/api/tests/conftest.py`, `services/discord/tests/conftest.py`, `services/web/playwright.config.ts`. Conflicts with current `python -m pytest tests infra/tests` only lane. |
| SLICE-R.03 | `.buildkite/pipeline-cluster.yml` or conditional cluster steps in `.buildkite/pipeline.yml`; nightly trigger if represented in repo; cluster-lane summary artifact path | `.buildkite/e2e-fullstack.yml`, `.buildkite/pipeline.yml`, runtime validator scripts under `infra/tests/validate_*_local.sh` only for exit semantics | Remove any green skip pattern that treats missing cluster/browser as success in the cluster lane | Reuses `infra/tests/e2e/run-fullstack.sh`, `infra/tests/e2e/lib/bringup.sh`, `infra/scripts/bring-up-local-channel.sh`. Conflicts with `--static-only` runtime claims. |
| SLICE-R.04 | Proposal-derived fixtures under `infra/tests/fixtures/contracts/`; rewritten contract pytests where needed; coverage-auditor before/after artifact | `infra/tests/test_local_buildkite_pipeline.py`, `infra/tests/test_kong_ingress_contract.py`, `infra/tests/test_backup_dr_contract.py`, `infra/tests/test_application_workloads_contract.py`, `infra/tests/test_auth_stack_contract.py`, `infra/tests/test_access_policy_contract.py`, `infra/tests/test_tenant_isolation_contract.py`, `infra/tests/test_observability_contract.py`, `infra/tests/test_web_ui_contract.py` | Delete captured assertions that cannot be re-derived from proposal text; do not leave compatibility snapshots | Reuses `plans/proposals/init-109..116*.md`, `docs/init-109..116*-handoff.md`, and current contract modules. Conflicts with resolver-output equality tests. |
| SLICE-R.05 | Step 6 artifacts; bootstrap fixture under `infra/tests/fixtures/channels/` if current fixture is insufficient | `infra/tests/validate_platform_bootstrap.sh`; `infra/tests/e2e/tests/01-cluster-up.sh`; possibly `infra/scripts/bring-up-local-channel.sh` only if independent tests fail | Delete or quarantine static resolver self-comparison blocks that cannot be justified | Reuses `plans/proposals/platform-bootstrap.md`, `plans/research/platform-bootstrap-hookpoints.md`, `infra/schemas/platform-channel*.json`, k3d module scripts. |
| SLICE-R.06 | Flux drift fixture and SOPS plaintext negative fixture | `infra/tests/e2e/tests/02-flux-reconciles.sh`; `infra/scripts/lint-sops-boundary.py` tests if absent; possibly `gitops/channels/local/generated/gitops-snapshot-marker.yaml` fixture expectations | Remove any SOPS assertion buried in bootstrap validator if it stays implementation-mirror only | Reuses `plans/proposals/gitops-foundation.md`, `gitops/flux/`, `gitops/sources/local/git-daemon.yaml`, Flux kustomizations. |
| SLICE-R.07 | Infisical sentinel fixture; Step 6 index for existing runtime flow | `infra/tests/e2e/tests/03-sops-bootstrap.sh`, `infra/tests/e2e/tests/04-infisical-runtime.sh`, `infra/scripts/bootstrap-infisical-*.sh` only if tests expose setup bugs | None expected | Reuses `gitops/bootstrap/*infisical*.enc.yaml`, `gitops/channels/local/infisical/**`, `infra/scripts/bootstrap-infisical-identity.sh`. |
| SLICE-R.08 | Step 6 artifact index for existing object-storage validator; payload fixture if not already embedded | `.buildkite/pipeline.yml` or cluster lane; `infra/tests/validate_object_storage_local.sh`; `infra/tests/e2e/tests/05-storage.sh` | None expected | Reuses the strong S3 round-trip and MinIO restart validator. Conflict is CI deadness, not test design. |
| SLICE-R.09 | Step 6 artifact index; certificate/hostname fixture if absent | `.buildkite/pipeline.yml` or cluster lane; `infra/tests/validate_tls_dns_local.sh`; `infra/tests/e2e/tests/06-tls-dns.sh` | None expected | Reuses cert-manager, step-ca, sample certificate manifests. Conflicts with future static chart/version proof if treated as runtime. |
| SLICE-R.10 | AppCluster claim fixture and webhook regression tests if not covered by R.01 | `infra/tests/validate_app_clusters_local.sh`; `infra/tests/e2e/tests/07-app-cluster.sh`; `gitops/channels/local/app-clusters/**` only if green tests require it | None expected | Depends on R.01 webhook fix. Reuses Crossplane XRD/composition/provider manifests and claim validator. |
| SLICE-R.11 | Negative probe fixtures for PSS, NetworkPolicy, RBAC | `infra/tests/validate_cluster_security_local.sh`; `infra/tests/e2e/tests/08-cluster-security.sh`; `gitops/channels/local/security/*.yaml` | Remove or narrow any policy that recreates R.01 webhook isolation | Reuses strong runtime denial tests. Must keep R.01 webhook reachability green while testing namespace isolation. |
| SLICE-R.12 | Step 6 artifact index for sample image delivery | `infra/tests/validate_container_delivery_local.sh`; `infra/tests/e2e/tests/09-image-registry.sh`; Buildkite image build steps | None expected | Reuses `containers/samples/registry-smoke/`, `infra/scripts/build-channel-image.sh`, local registry config. |
| SLICE-R.13 | Pipeline YAML fixtures for runner tests; token-path fixture | `infra/tests/test_local_buildkite_pipeline.py`; `infra/tests/validate_buildkite_cicd_local.sh`; `infra/scripts/run-local-buildkite-pipeline.py`; `.buildkite/pipeline.yml` | Delete exact ordered step-key snapshot assertion; remove literal-only static checks if unrecoverable | Reuses local runner semantics and Buildkite agent manifests. Conflicts with exact step-list tests. |
| SLICE-R.14 | Host route/certificate/backend health fixture | `infra/tests/test_kong_ingress_contract.py`; `infra/tests/validate_kong_ingress_local.sh`; `infra/tests/e2e/tests/11-ingress.sh`; `gitops/channels/local/ingress/**` | Delete chart/version-only proof if not paired with behavior | Reuses Kong manifests, MinIO default service route, TLS/DNS from R.09, registry from R.12. |
| SLICE-R.15 | SQL proof fixture and psql client fixture | `infra/tests/validate_data_plane_local.sh`; `infra/tests/e2e/tests/12-data-plane.sh`; `gitops/channels/local/data-plane/**`; CNPG-related policies | Delete static-only claims that imply migration/connectivity proof | Reuses CNPG, Atlas, sample-app migration manifests. Needs R.01 awareness for `cnpg-system` policy. |
| SLICE-R.16 | Seed SQL, manual Backup, restore-cluster fixture | `infra/tests/test_backup_dr_contract.py`; `infra/tests/validate_backup_dr_local.sh`; `infra/tests/e2e/tests/13-backup-dr.sh`; `infra/scripts/run-cnpg-restore-drill.sh` | Delete scheduled-backup-only tests if represented as restore proof | Reuses backup handoff docs, object storage from R.08, data plane from R.15. |
| SLICE-R.17 | Runtime app fixture for API/Discord pods, DB seed, ingress proof | `infra/tests/test_application_workloads_contract.py`; `infra/tests/validate_application_workloads_local.sh`; `infra/tests/e2e/tests/14-application-workloads.sh`; `gitops/channels/local/applications/server-manager/**`; containers | Delete literal image-tag assertions if not fixture inputs | Reuses service containers, server-manager manifests, MinIO bucket job, migrations. |
| SLICE-R.18 | New auth contract artifact; Cedar decision fixture; Pomerium identity/header fixture; browser auth fixture | `infra/tests/test_auth_stack_contract.py`; `infra/tests/validate_auth_stack_local.sh`; `infra/tests/e2e/tests/15-auth-stack.sh`; `gitops/channels/local/auth/**`; `services/api/app/infrastructure/authz.py`; protected endpoint tests | Delete chart/version-only auth-stack tests; no compatibility path for old auth behavior | DECOMPOSE slice. Reuses protected API tests and Playwright browser-flow harness. Product-code diff cap applies. |
| SLICE-R.19 | Cedar matrix fixture and bundle-load fixture | `infra/tests/test_access_policy_contract.py`; `infra/tests/validate_access_policy_local.sh`; `infra/tests/e2e/tests/16-access-policy.sh`; `policy/cedar/**`; `gitops/channels/local/access-policy/**`; API authz tests | Delete policy-id literal tests that do not assert allow/deny behavior | DECOMPOSE slice. Reuses Cedar policies, service identities, and protected authz endpoint. |
| SLICE-R.20 | Tenant principals/resources fixture; Kubernetes deny fixture | `infra/tests/test_tenant_isolation_contract.py`; `infra/tests/validate_tenant_isolation_local.sh`; `infra/tests/e2e/tests/17-tenant-isolation.sh`; `gitops/channels/local/tenants/**`; `infra/scripts/spawn_platform_channel.py` | Delete label-dict snapshots if no deny behavior is asserted | DECOMPOSE slice. Reuses tenant sample namespaces, RBAC, NetworkPolicies, Infisical secrets. |
| SLICE-R.21 | Prometheus target query, sample alert, sample log, dashboard fixture | `infra/tests/test_observability_contract.py`; `infra/tests/validate_observability_local.sh`; `infra/tests/e2e/tests/18-observability.sh`; `gitops/channels/local/observability/**` | Delete ordered ServiceMonitor list snapshots if not contract-derived | Reuses observability stack. Must not recreate R.01 webhook isolation through empty-selector scrape policy. |
| SLICE-R.22 | Web component/form fixtures; API fake/recording fixture; browser route fixture | `infra/tests/test_web_ui_contract.py`; `infra/tests/validate_web_ui_local.sh`; `services/web/tests/compat.spec.ts`; `services/web/src/**`; `gitops/channels/local/applications/web/**`; `infra/tests/e2e/tests/19-web-ui.sh` | Delete demo-heading-only Playwright assertions unless retained as fixture-specific smoke | DECOMPOSE slice. Reuses Playwright config, Vite config, app routes, web container. |
| SLICE-R.23 | Re-authored 19 E2E test files from per-layer contracts; Step 6b output index mapping each test | `infra/tests/e2e/tests/*.sh`; `infra/tests/e2e/run-fullstack.sh` only for harness defects; `infra/tests/e2e/lib/**` only for framework bugs; `.buildkite/e2e-fullstack.yml`; `docs/infra-e2e-status.md` | Delete WIP test bodies that came from INIT-119 same-run scaffold; no stale status doc | Reuses E2E architecture, not current test bodies as canonical contracts. Product-code diff cap applies. |
| SLICE-R.24 | Buildkite verdict-grep script or inline steps; scratch report fixtures; expected report fixtures for tests | `.buildkite/pipeline.yml`; possibly `.buildkite/e2e-fullstack.yml`; formal gate artifact paths under `.tmp/recovery/*/phase6/` | Delete any advisory-only "artifact upload equals gate" pattern | Reuses red/green/process-tree reports. Conflicts with current absence of blocking wrapper and missing Phase 6 artifacts. |
| SLICE-R.25 | Legacy classification report; replacement tests for DELETE_AND_REWRITE cases; migration commits moving tests to service owners | `tests/*.py`; `services/api/tests/*.py`; `services/discord/tests/*.py`; `.buildkite/pipeline.yml`; possibly `discord_cli.py` tests if retained as read-only CLI | Delete old root paths after migration; delete `tests/test_discord_cli.py` once replacement or residual exists; no re-export aliases | Reuses service conftests, API testcontainers, Discord `httpx.MockTransport`, contracts under `services/*/app/contracts`. Conflicts with root daemon tests and mock-everything CLI tests. |

### Hookpoint notes by surface

- Buildkite currently has one main pipeline, `.buildkite/pipeline.yml`, and one
  separate full-stack pipeline, `.buildkite/e2e-fullstack.yml`. R.02 modifies
  the main pipeline; R.03 decides whether cluster runtime is a new pipeline or
  conditional main-pipeline steps; R.23 preserves full-stack architecture; R.24
  adds the formal verdict wrapper.

- The main pipeline currently runs `python -m pytest tests infra/tests`, so
  root daemon and infra pytests are visible while `services/api/tests`,
  `services/discord/tests`, and web Playwright tests are not. This is the
  central R.02 extension point.

- Runtime shell validators are already organized by layer under `infra/tests`.
  R.03 should not duplicate them; it should make their cluster-required modes
  executable, artifact-producing, and non-skipping in CI.

- E2E shell test files under `infra/tests/e2e/tests/` are not trusted as
  contracts. Their filenames and harness integration survive as useful
  topology, but R.23 re-authors body assertions from R.05-R.22 output indexes.

- The shell harness functions in `infra/tests/e2e/lib/assertions.sh` are useful
  but encode `SKIP` as exit 0. R.03/R.23 must define whether a skip is allowed
  per lane. For cluster-required and browser-required flows, skip should be
  fail/block, not green.

- The Crossplane RCA points at live kube-router behavior, not just manifests.
  R.01 tests should include in-cluster same-namespace probe, observability
  namespace positive probe, and API admission dry-run proof.

- R.01 should add no namespace-wide default allow. The extension point is the
  existing observability NetworkPolicy file; the fix should add the narrow
  webhook or same-namespace ingress required by the independent tests.

- The operator webhook services live in rendered vendor manifests:
  Crossplane under `gitops/channels/local/app-clusters/crossplane/core/rendered/`,
  cert-manager under `gitops/channels/local/tls/cert-manager/rendered/`, and
  CNPG under `gitops/channels/local/data-plane/cnpg/rendered/`. Do not edit
  rendered vendor YAML by hand unless the repo's render workflow owns it.

- R.04 and R.13 share the harmful Buildkite snapshot. R.04 can remove the bad
  test-level assertion from evidence accounting; R.13 should replace it with
  local runner behavior tests.

- The proposal/handoff files for INIT-109..116 are present under
  `plans/proposals/`, `plans/research/`, and `docs/`. They are the source of
  truth for captured contract pytest rewrites. R.04 should not use
  `infra/scripts/resolve_platform_channel.py` output as expected values.

- INIT-101..108 do not all have same-shaped local proposals under
  `plans/proposals/`; use the named platform/gitops/app-cluster proposals,
  audit-history files, handoffs where present, and existing hookpoint research
  rather than guessing missing behavior.

- `infra/scripts/lint-sops-boundary.py` exists as a reusable SOPS boundary
  tool. R.06/R.07 need negative fixtures that prove it fails on a leak, not a
  same-tree pass-only assertion.

- `infra/scripts/run-cnpg-restore-drill.sh` exists and is the natural R.16
  hookpoint for restore behavior. If the script is incomplete or stale, R.16
  should repair it under independent backup/restore tests rather than writing a
  parallel restore harness.

- `infra/scripts/build-channel-image.sh` and
  `infra/scripts/build-server-manager-images.sh` are shared by R.12, R.17,
  R.22, and R.23. Keep image tag values as fixture inputs, not behavior
  assertions.

- API service tests already use the app factory and repositories against real
  Postgres. R.25 modernization should prefer preserving this pattern over
  replacing API tests with mocks.

- Discord service tests have two patterns: `httpx.MockTransport` adapter tests,
  which are useful, and MockGuild/mock-call tests, which are captured. R.25
  should split those outcomes file by file instead of downgrading the whole
  suite.

- Web tests have Playwright infrastructure but no API fixture layer. R.02 only
  wires current commands; R.22 owns the missing fake/recording API and form
  behavior coverage.

- Legacy root daemon tests should not be kept as aliases to service tests. If a
  behavior belongs to `services/discord`, migrate the test there and delete the
  root path in the same commit.

- No slice needs a Discord-visible Tier 3 action. All mutation targets in this
  recovery are local files, local CI, and local clusters.

## Closed namespace list (SLICE-R.01)

The actual empty-selector `allow-observability-scrape` pattern appears only in
`gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml`.
The closed list is 11 namespaces. For SLICE-R.01 admission-webhook reachability,
the operator-webhook namespaces in this list are `crossplane-system`,
`cert-manager`, and `cnpg-system`. The remaining namespaces share the same
isolation pattern and should be regression-checked only for their relevant
runtime listeners, not treated as Kubernetes admission webhook services unless
Step 6a finds such a webhook there.

| Namespace | Has allow-observability-scrape pattern | Verified by |
|---|---|---|
| `flux-system` | Yes | `observability-networkpolicies.yaml` lines 93-108; no rendered admission webhook service found in tree |
| `crossplane-system` | Yes; R.01 operator-webhook scope | `observability-networkpolicies.yaml` lines 110-125; rendered `crossplane-webhooks` service and webhook config in Crossplane manifest |
| `cert-manager` | Yes; R.01 operator-webhook scope | `observability-networkpolicies.yaml` lines 127-142; rendered `cert-manager-webhook` service and webhook config in cert-manager manifest |
| `cnpg-system` | Yes; R.01 operator-webhook scope | `observability-networkpolicies.yaml` lines 144-159; rendered CNPG operator/webhook objects in CNPG manifest |
| `kong-system` | Yes | `observability-networkpolicies.yaml` lines 161-176; ingress-controller namespace, no admission webhook service found in local tree |
| `minio-system` | Yes | `observability-networkpolicies.yaml` lines 178-193; MinIO runtime namespace, no admission webhook service found |
| `infisical-system` | Yes | `observability-networkpolicies.yaml` lines 195-210; Infisical operator/server namespace, no local admission webhook service found |
| `server-manager` | Yes | `observability-networkpolicies.yaml` lines 212-227; application namespace, not an admission webhook namespace |
| `auth-system` | Yes | `observability-networkpolicies.yaml` lines 229-244; Authentik/Pomerium/OPAL namespace, no admission webhook service found |
| `sample-app-db` | Yes | `observability-networkpolicies.yaml` lines 246-261; sample CNPG workload namespace, not the CNPG operator webhook namespace |
| `buildkite-agent` | Yes | `observability-networkpolicies.yaml` lines 263-278; CI agent namespace, not an admission webhook namespace |

Equivalent NetworkPolicy files were also walked:
`app-clusters/claims/networkpolicies.yaml`, `applications/server-manager/networkpolicies.yaml`,
`applications/web/networkpolicy.yaml`, `auth/networkpolicies.yaml`,
`cicd/networkpolicy.yaml`, `ingress/default-services/minio/networkpolicy.yaml`,
`security/data-plane-networkpolicies.yaml`, `security/infisical-networkpolicies.yaml`,
`security/minio-networkpolicies.yaml`, `security/restricted-default-deny.yaml`,
`security/dns-egress.yaml`, and all tenant `networkpolicies.yaml` files. None
adds another `allow-observability-scrape` namespace.

## SLICE-R.25 contract sources

Verdicts here are hookpoint recommendations for R.25, not final
classification. The discipline for every surviving test is: re-derive expected
behavior from the named proposal/contract, then update or migrate the test; do
not preserve implementation snapshots merely because the file currently passes.

| Legacy test | Verdict | Contract source if MODERNIZE/MIGRATE |
|---|---|---|
| `tests/test_daemon_init.py` | DELETE_AND_REWRITE | `proposals/13-daemon-init.md`, replaced by `services/discord/app/contracts/runtime.py` and `proposals/25-discord-main.md` if daemon package proof survives |
| `tests/test_daemon_config.py` | MIGRATE | `proposals/14-config.md`, `proposals/20-settings.md`, `proposals/23-discord-settings.md`, `services/api/app/contracts/runtime_settings.py`, `services/discord/app/contracts/runtime_settings.py` |
| `tests/test_daemon_db.py` | MIGRATE | `proposals/15-db.md`, API persistence contracts in `services/api/app/contracts/persistence.py`, current Alembic migration contract |
| `tests/test_daemon_claim.py` | MIGRATE | `proposals/16-claim.md`, ticket/application ownership in `services/api/app/contracts/tickets.py` and Discord interaction contracts |
| `tests/test_daemon_applications.py` | MIGRATE | `proposals/18-applications.md`, `services/api/app/contracts/applications.py`, `services/discord/app/contracts/application_submission.py` |
| `tests/test_daemon_entry.py` | DELETE_AND_REWRITE | `proposals/17-daemon-entry.md`, `proposals/24-discord-bot.md`, `proposals/25-discord-main.md` |
| `tests/test_discord_cli.py` | DELETE_AND_REWRITE | `proposals/05-discord-cli.md` for read-only CLI behavior; replacement must use a real/recorded Discord API boundary or residual-risk disposition |
| `services/api/tests/test_activity_model.py` | MODERNIZE | `plans/proposals/activity-audit-model.md`, `services/api/app/contracts/activity.py`, `services/api/app/contracts/audit.py` |
| `services/api/tests/test_application_boundaries.py` | KEEP_AS_IS | Application boundary contract in `services/api/app/contracts/applications.py` and current API endpoint contracts |
| `services/api/tests/test_application_interviews.py` | KEEP_AS_IS | `services/api/app/contracts/applications.py`, interview lifecycle endpoint contracts |
| `services/api/tests/test_applications.py` | KEEP_AS_IS | Application intake contract in `services/api/app/contracts/applications.py` |
| `services/api/tests/test_archive_boundaries.py` | KEEP_AS_IS | SLICE-023 archive AC1-AC4 docstrings, `services/api/app/contracts/chapters.py` |
| `services/api/tests/test_audit_api.py` | KEEP_AS_IS | SLICE-009 WU-016A, `services/api/app/contracts/audit.py` |
| `services/api/tests/test_audit_foundation.py` | KEEP_AS_IS | WU-003 audit/correlation foundation, `services/api/app/contracts/audit.py` |
| `services/api/tests/test_authority.py` | KEEP_AS_IS | SLICE-008 / WU-014 authority lifecycle, `services/api/app/contracts/authority.py` |
| `services/api/tests/test_authority_enforcement.py` | KEEP_AS_IS | WU-015A authority guard AC3, `services/api/app/contracts/authority.py` |
| `services/api/tests/test_authority_foundation.py` | KEEP_AS_IS | WU-004 authority foundation, `services/api/app/contracts/authority.py` |
| `services/api/tests/test_authority_override_audit.py` | KEEP_AS_IS | WU-015B override audit policy AC4, `services/api/app/contracts/authority.py` |
| `services/api/tests/test_authority_transfer.py` | KEEP_AS_IS | Authority transfer contract in `services/api/app/contracts/authority.py` |
| `services/api/tests/test_chapter_archive_execution.py` | KEEP_AS_IS | SLICE-023 archive execution, `services/api/app/contracts/chapters.py` |
| `services/api/tests/test_chapter_archive_plan.py` | KEEP_AS_IS | SLICE-023 archive plan AC3, `services/api/app/contracts/chapters.py`, `scheduler.py` |
| `services/api/tests/test_chapter_governance.py` | KEEP_AS_IS | SLICE-023 governance lifecycle, `services/api/app/contracts/chapters.py` |
| `services/api/tests/test_chapter_lifecycle.py` | KEEP_AS_IS | SLICE-013 chapter lifecycle, `services/api/app/contracts/chapters.py` |
| `services/api/tests/test_chapter_role_foundation.py` | KEEP_AS_IS | WU-007B chapter role foundation, `services/api/app/contracts/chapter_roles.py` |
| `services/api/tests/test_chapter_template_foundation.py` | KEEP_AS_IS | WU-007A template foundation AC3, `services/api/app/contracts/chapter_templates.py` |
| `services/api/tests/test_chapter_templates.py` | KEEP_AS_IS | Chapter template CRUD contract, `services/api/app/contracts/chapter_templates.py` |
| `services/api/tests/test_compliance_evaluation_worker.py` | KEEP_AS_IS | SLICE-022 compliance evaluation worker, `services/api/app/contracts/compliance.py` |
| `services/api/tests/test_compliance_evidence.py` | KEEP_AS_IS | Compliance evidence AC2, `services/api/app/contracts/compliance.py` |
| `services/api/tests/test_compliance_ocr_correct.py` | KEEP_AS_IS | Compliance OCR correction AC3, `services/api/app/contracts/compliance_corrections.py` |
| `services/api/tests/test_compliance_ocr_extract.py` | KEEP_AS_IS | Compliance OCR extraction AC2, `services/api/app/contracts/compliance_extraction.py` |
| `services/api/tests/test_compliance_review_api.py` | KEEP_AS_IS | Compliance review API, `services/api/app/contracts/compliance.py` |
| `services/api/tests/test_compliance_rules.py` | KEEP_AS_IS | Compliance rule AC1, `services/api/app/contracts/compliance.py` |
| `services/api/tests/test_conftest.py` | MODERNIZE | `proposals/28-conftest.md`, `services/api/app/contracts/testing.py`; keep only if it protects CI fixture behavior |
| `services/api/tests/test_contracts_base.py` | MODERNIZE | `proposals/22-contracts-base.md`; verify no backward-compatibility exports from contract modules |
| `services/api/tests/test_contracts_chapter_lifecycle.py` | MODERNIZE | `proposals/26-chapters-contract.md`, `services/api/app/contracts/chapters.py` |
| `services/api/tests/test_deferred_effect_foundation.py` | KEEP_AS_IS | SLICE-004 WU-008B deferred effects, `services/api/app/contracts/scheduler.py` |
| `services/api/tests/test_endpoints_chapters_stubs.py` | DELETE_AND_REWRITE | Replace stub-response assertions from `proposals/27-chapter-endpoints.md` with real endpoint contract tests |
| `services/api/tests/test_factory.py` | MODERNIZE | `proposals/21-factory.md`, `services/api/app/core/factory.py`, runtime readiness contract |
| `services/api/tests/test_forms.py` | MODERNIZE | `proposals/18-applications.md`, `services/api/app/contracts/applications.py`; remove schema literal capture |
| `services/api/tests/test_harness.py` | MODERNIZE | `proposals/28-conftest.md`, `services/api/app/contracts/testing.py`; keep only as fixture contract |
| `services/api/tests/test_leadership_context.py` | KEEP_AS_IS | Authority/leadership context contracts in `services/api/app/contracts/authority.py` |
| `services/api/tests/test_leadership_handoff_applications.py` | KEEP_AS_IS | SLICE-024 leadership handoff applications, `services/api/app/contracts/applications.py` |
| `services/api/tests/test_leadership_handoff_tickets.py` | KEEP_AS_IS | SLICE-024 leadership handoff tickets, `services/api/app/contracts/tickets.py` |
| `services/api/tests/test_members.py` | KEEP_AS_IS | Member contract in `services/api/app/contracts/members.py` |
| `services/api/tests/test_mutations.py` | KEEP_AS_IS | Mutation contract in `services/api/app/contracts/mutations.py` |
| `services/api/tests/test_notification_delivery_worker.py` | KEEP_AS_IS | Notification delivery worker, `services/api/app/contracts/notifications.py` |
| `services/api/tests/test_notification_event_contract.py` | MODERNIZE | WU-003B notification event envelope, `services/api/app/contracts/notifications.py`; re-check literal shape against proposal |
| `services/api/tests/test_notification_materialization.py` | KEEP_AS_IS | Notification materialization contract, `services/api/app/contracts/notifications.py` |
| `services/api/tests/test_notification_rules.py` | KEEP_AS_IS | Notification rule contract, `services/api/app/contracts/notifications.py` |
| `services/api/tests/test_operational_views.py` | KEEP_AS_IS | SLICE-017 read-model contract, `services/api/app/contracts/read_models.py` |
| `services/api/tests/test_permission_drift.py` | KEEP_AS_IS | SLICE-014 drift detection, `services/api/app/contracts/permissions.py` |
| `services/api/tests/test_permission_intents.py` | KEEP_AS_IS | Permission intents contract, `services/api/app/contracts/permissions.py` |
| `services/api/tests/test_permission_reconciliation_api.py` | KEEP_AS_IS | Permission reconciliation API, `services/api/app/contracts/permissions.py` |
| `services/api/tests/test_permission_temporary_api.py` | KEEP_AS_IS | SLICE-020 temporary permissions, `services/api/app/contracts/permissions.py` |
| `services/api/tests/test_permission_temporary_worker.py` | KEEP_AS_IS | Temporary permission worker, `services/api/app/contracts/permissions.py` |
| `services/api/tests/test_persistence.py` | KEEP_AS_IS | Persistence/migration contract in `services/api/app/contracts/persistence.py` and Alembic head |
| `services/api/tests/test_policies.py` | KEEP_AS_IS | SLICE-010 WU-017 policy preview/confirm/current, `services/api/app/contracts/policies.py` |
| `services/api/tests/test_policy_foundation.py` | KEEP_AS_IS | WU-005 policy preview-confirm foundation, `services/api/app/contracts/policies.py` |
| `services/api/tests/test_protected_authz.py` | KEEP_AS_IS | INIT-114 protected authz API contract, `services/api/app/contracts/authz.py` |
| `services/api/tests/test_read_models.py` | KEEP_AS_IS | Read-model contract, `services/api/app/contracts/read_models.py` |
| `services/api/tests/test_roster.py` | KEEP_AS_IS | Roster contract, `services/api/app/contracts/roster.py` |
| `services/api/tests/test_scheduler_foundation.py` | MODERNIZE | SLICE-004 WU-008A scheduler foundation, `services/api/app/contracts/scheduler.py`; remove dict-shape capture |
| `services/api/tests/test_settings.py` | MODERNIZE | `proposals/20-settings.md`, `services/api/app/contracts/runtime_settings.py` |
| `services/api/tests/test_succession_plan.py` | KEEP_AS_IS | Succession plan contract in `services/api/app/contracts/authority.py` |
| `services/api/tests/test_ticket_boundaries.py` | KEEP_AS_IS | Ticket boundary AC4/D17, `services/api/app/contracts/tickets.py` |
| `services/api/tests/test_ticket_categories.py` | KEEP_AS_IS | Ticket category contract, `services/api/app/contracts/ticket_categories.py` |
| `services/api/tests/test_ticket_create.py` | KEEP_AS_IS | Ticket creation contract, `services/api/app/contracts/tickets.py` |
| `services/api/tests/test_ticket_initial_message_events.py` | KEEP_AS_IS | Ticket event emission contract, `services/api/app/contracts/tickets.py` and `notifications.py` |
| `services/api/tests/test_ticket_messages.py` | KEEP_AS_IS | Ticket message contract, `services/api/app/contracts/ticket_messages.py` |
| `services/api/tests/test_ticket_sla.py` | KEEP_AS_IS | Ticket SLA contract, `services/api/app/contracts/ticket_categories.py`, `tickets.py`, `notifications.py` |
| `services/api/tests/test_ticket_transitions.py` | KEEP_AS_IS | Ticket transition contract, `services/api/app/contracts/tickets.py` |
| `services/api/tests/test_trust.py` | KEEP_AS_IS | Trust contract, `services/api/app/contracts/trust.py` |
| `services/api/tests/test_trust_recompute.py` | KEEP_AS_IS | Trust recompute contract, `services/api/app/contracts/trust.py` |
| `services/api/tests/test_trust_signals.py` | KEEP_AS_IS | Trust signal aggregation contract, `services/api/app/contracts/trust.py` |
| `services/api/tests/test_web_identity.py` | KEEP_AS_IS | INIT-114 web identity / Pomerium header pass-through, `services/api/app/contracts/web.py` and `authz.py` |
| `services/discord/tests/test_api_context.py` | KEEP_AS_IS | SLICE-009 WU-016B Discord correlation adapter, `services/discord/app/contracts/audit.py` |
| `services/discord/tests/test_api_transport.py` | KEEP_AS_IS | WU-009D / AC3 API transport, `services/discord/app/contracts/api_transport.py` |
| `services/discord/tests/test_application_interview.py` | KEEP_AS_IS | Application interview interaction contract, `services/discord/app/contracts/application_interview.py` |
| `services/discord/tests/test_application_review.py` | MODERNIZE | Application review interaction contract, `services/discord/app/contracts/application_review.py`; remove copied response-body literals |
| `services/discord/tests/test_application_submission.py` | MODERNIZE | Application submission contract, `services/discord/app/contracts/application_submission.py` |
| `services/discord/tests/test_application_waitlist.py` | MODERNIZE | Application waitlist contract, `services/discord/app/contracts/application_waitlist.py` |
| `services/discord/tests/test_bot.py` | MODERNIZE | `proposals/24-discord-bot.md`, `services/discord/app/contracts/runtime.py`; keep only intent/runtime requirements |
| `services/discord/tests/test_chapter_provisioning.py` | MODERNIZE | SLICE-013 chapter provisioning contract, `services/discord/app/contracts/chapters.py`; replace MockGuild call snapshots |
| `services/discord/tests/test_harness.py` | MODERNIZE | `proposals/28-conftest.md`, `services/discord/app/contracts/testing.py` |
| `services/discord/tests/test_interaction_framework.py` | KEEP_AS_IS | WU-009C / AC4 interaction registry, `services/discord/app/contracts/interactions.py` |
| `services/discord/tests/test_main.py` | DELETE_AND_REWRITE | `proposals/25-discord-main.md`, command registry contract; delete literal command-order snapshot |
| `services/discord/tests/test_notifications.py` | MODERNIZE | SLICE-015 notification adapter, `services/discord/app/contracts/notifications.py`; replace mock-call proof |
| `services/discord/tests/test_onboarding.py` | MODERNIZE | Onboarding/member join contract, `services/discord/app/contracts/onboarding.py` |
| `services/discord/tests/test_permission_reconciliation_adapter.py` | MODERNIZE | Permission reconciliation adapter, `services/discord/app/contracts/permissions.py`; reduce MockGuild call snapshots |
| `services/discord/tests/test_roster_sync.py` | MODERNIZE | Roster sync contract, `services/discord/app/contracts/roster.py` |
| `services/discord/tests/test_settings.py` | MODERNIZE | `proposals/23-discord-settings.md`, `services/discord/app/contracts/runtime_settings.py` |
| `services/discord/tests/test_tickets.py` | MODERNIZE | Ticket interaction contract, `services/discord/app/contracts/tickets.py`; replace mock-heavy channel assertions |

## Service test infrastructure inventory

- `services/api/` has strong fixture infrastructure already.
  `services/api/pyproject.toml` declares `httpx`, `pytest`,
  `pytest-asyncio`, and `testcontainers[postgres]` dev dependencies.
  `services/api/tests/conftest.py` provides session and per-test
  `PostgresContainer("postgres:16")`, Alembic upgrade fixtures,
  `fresh_migrated_postgres_db`, FastAPI app factory, `TestClient`, and
  environment setup. SLICE-R.02 needs a Buildkite step that installs API
  dev dependencies, runs Alembic-backed tests, checks Docker availability
  before counting testcontainers tests as gated, and preserves logs on
  collection/runtime failure. It does not need a new database fixture layer.

- `services/discord/` has useful isolated adapter fixtures, but the suite is
  not enough to call all behavior VERIFIED. `services/discord/pyproject.toml`
  declares `httpx`, `pytest`, `pytest-asyncio`, `pytest-cov`, and
  `pytest-mock`. `services/discord/tests/conftest.py` provides a real
  `HumilityBot` fixture with test settings, an `interaction_factory`, and an
  `httpx.MockTransport` API client stub that records requests and queues
  responses. SLICE-R.02 needs a Buildkite step for this suite and must label
  CAPTURED mock-heavy tests as running but not promoted. No Docker or external
  Discord server fixture exists, and none should be added in R.02.

- `services/web/` has Playwright/Vite infrastructure but little test depth.
  `services/web/package.json` exposes `build`, `typecheck`, `lint`,
  `format`, `test`, and `test:compat`. `services/web/playwright.config.ts`
  builds and starts preview at `127.0.0.1:4173`; `vite.config.ts` proxies
  `/api` to `VITE_API_BASE_URL` or `localhost:8000`. SLICE-R.02 can wire
  `npm ci`, `npm run typecheck`, and `npm test` or `npm run test:compat`,
  but browser installation/cache availability must be a visible BLOCKED or
  red signal in CI. Mock API/server-recording fixtures are not present yet;
  those belong to SLICE-R.22, not R.02.

## INIT-119 architecture survival map

| File | Survives | Why or replaced by |
|---|---|---|
| `.buildkite/e2e-fullstack.yml` | Yes, modified | It is the existing full-stack lane architecture. R.23/R.03 should make invocation/cadence honest and preserve artifact paths. |
| `infra/tests/e2e/run-fullstack.sh` | Yes, modified only for harness defects | It already handles bring-up, teardown, per-test logs, diagnostics, and status doc generation. Test bodies are re-derived; harness stays. |
| `infra/tests/e2e/lib/assertions.sh` | Yes, modified only for gate semantics | Useful shared `e2e_init`, pass/fail, `require_cluster`, diagnostics, and validator wrappers. `e2e_skip_flow` may need lane-specific fail/block semantics. |
| `infra/tests/e2e/lib/bringup.sh` | Yes | Existing local cluster bring-up, image pre-pull, local image build, and readiness functions are reusable. |
| `infra/tests/e2e/lib/teardown.sh` | Yes | Teardown is infrastructure, not a test contract; keep unless cleanup is proven broken. |
| `infra/tests/e2e/lib/playwright/package.json` | Yes | Browser harness dependency boundary survives. |
| `infra/tests/e2e/lib/playwright/run-browser-flow.sh` | Yes, modified only if browser availability semantics are wrong | It obtains test auth credentials and launches browser-flow. Missing credentials currently exit `75`; R.23 must define whether that is BLOCKED or FAIL. |
| `infra/tests/e2e/lib/playwright/browser-flow.mjs` | Yes as harness, assertions re-derived | Login/session mechanics survive. Flow targets and page assertions are re-derived from R.18/R.22 contracts. |
| `infra/tests/e2e/playwright/.gitignore` | Yes | Runtime sessions/artifacts boundary. |
| `infra/tests/e2e/tests/01-cluster-up.sh` | Re-derived | Current body is not canonical, but cluster/node/DNS proof is aligned with R.05. |
| `infra/tests/e2e/tests/02-flux-reconciles.sh` | Re-derived | Flux Ready proof survives as intent, but drift/SOPS expectations come from R.06. |
| `infra/tests/e2e/tests/03-sops-bootstrap.sh` | Re-derived | SOPS sentinel proof survives as intent, contract comes from R.06/R.07. |
| `infra/tests/e2e/tests/04-infisical-runtime.sh` | Re-derived | Infisical secret round-trip survives as intent, contract comes from R.07. |
| `infra/tests/e2e/tests/05-storage.sh` | Re-derived wrapper | Keep wrapper shape if it delegates to R.08 validator with Step 6b index. |
| `infra/tests/e2e/tests/06-tls-dns.sh` | Re-derived wrapper | Keep wrapper shape if it delegates to R.09 validator and adds contract-derived DNS proof. |
| `infra/tests/e2e/tests/07-app-cluster.sh` | Re-derived wrapper | Must depend on R.01 and R.10 contracts. |
| `infra/tests/e2e/tests/08-cluster-security.sh` | Re-derived wrapper | Must include R.11 denial proofs and R.01 regression guard. |
| `infra/tests/e2e/tests/09-image-registry.sh` | Re-derived wrapper | Must map to R.12 contract. |
| `infra/tests/e2e/tests/10-buildkite.sh` | Re-derived | Must map to R.13 runner/agent contract, not exact pipeline snapshot. |
| `infra/tests/e2e/tests/11-ingress.sh` | Re-derived wrapper | Must map to R.14 route/TLS/backend contract. |
| `infra/tests/e2e/tests/12-data-plane.sh` | Re-derived wrapper | Must map to R.15 CNPG/Atlas/psql contract. |
| `infra/tests/e2e/tests/13-backup-dr.sh` | Re-derived | Must prove restore equality or block if contract is insufficient. |
| `infra/tests/e2e/tests/14-application-workloads.sh` | Re-derived | Must assert API ready, DB/migration, ingress, Discord pod. |
| `infra/tests/e2e/tests/15-auth-stack.sh` | Re-derived | Browser/auth flow contract from R.18; missing browser cannot be green. |
| `infra/tests/e2e/tests/16-access-policy.sh` | Re-derived | Cedar matrix behavior from R.19, not policy-id literals. |
| `infra/tests/e2e/tests/17-tenant-isolation.sh` | Re-derived | Cross-tenant negative path from R.20. |
| `infra/tests/e2e/tests/18-observability.sh` | Re-derived | Prometheus/log/alert behavior from R.21. |
| `infra/tests/e2e/tests/19-web-ui.sh` | Re-derived | Route/form/auth behavior from R.22. |
| `docs/infra-e2e-status.md` | Regenerated | Survives as generated report, but R.23 must overwrite from actual run and not accept stale committed status. |

## Implementation blockers (B1..BN)

- B1: SLICE-R.01 cannot proceed to policy edits if the first independent
  reachability tests still fail after the hypothesized NetworkPolicy isolation
  is corrected. The proposal's A1 consequence applies: stop and return to RCA.

- B2: The R.01 namespace list is now closed for the pattern at 11 namespaces,
  but Step 6a must decide whether non-operator same-pattern namespaces receive
  only regression smoke or full webhook admission tests. Hookpoint
  recommendation: full admission tests only for `crossplane-system`,
  `cert-manager`, and `cnpg-system`.

- B3: SLICE-R.02 is blocked from promoting API tests if Buildkite workers lack
  Docker access for `testcontainers[postgres]`. Missing Docker is BLOCKED, not
  green.

- B4: SLICE-R.02 is blocked from promoting web tests if Playwright browser
  installation/cache is absent and the command silently skips. Browser absence
  must be red or BLOCKED.

- B5: SLICE-R.03 is blocked if there is no cluster-equipped Buildkite queue or
  no supported way to run k3d/Docker in CI. The lane itself is mandatory; only
  bounded validator subpaths can be residual.

- B6: SLICE-R.04 and R.13 are blocked from retaining exact pipeline step-list
  assertions. Those assertions must be deleted or rewritten into behavioral
  runner semantics.

- B7: SLICE-R.16 is blocked if backup restore semantics cannot be found in
  proposal/handoff text. Do not invent RPO/RTO or restore behavior in Step 6b.

- B8: SLICE-R.18/R.19/R.20/R.22/R.23 must respect the 200-line/5-file
  product-code cap. If independent tests show a larger implementation repair,
  the slice stops for a separate proposal.

- B9: SLICE-R.23 is blocked until R.05..R.22 contracts exist. Its test bodies
  must be generated from those contracts, not copied from current WIP E2E files.

- B10: SLICE-R.24 cannot enforce missing Phase 6 artifacts until each slice has
  a predictable scratch path. Define the path convention before writing the
  Buildkite grep wrapper.

- B11: SLICE-R.25 cannot delete root legacy tests unless replacement tests or
  residual-risk dispositions exist. This especially applies to
  `tests/test_discord_cli.py` because it is harmful but still covers a read-only
  CLI surface.

## Cross-slice dependencies

- SLICE-R.01: no slice prerequisites after Phase 5; blocks R.10 and guards
  R.11/R.21.
- SLICE-R.02: no slice prerequisites; enables service CI visibility and R.05,
  R.13, R.24, R.25.
- SLICE-R.03: depends on R.01 when Crossplane blocks full-stack reconciliation.
- SLICE-R.04: no slice prerequisites after hookpoints; informs R.13-R.22
  rewrite discipline and R.25 modernization discipline.
- SLICE-R.05: depends on R.02.
- SLICE-R.06: depends on R.05.
- SLICE-R.07: depends on R.06.
- SLICE-R.08: depends on R.03.
- SLICE-R.09: depends on R.03.
- SLICE-R.10: depends on R.01 and R.03.
- SLICE-R.11: depends on R.03 and must keep R.01 green.
- SLICE-R.12: depends on R.03.
- SLICE-R.13: depends on R.02.
- SLICE-R.14: depends on R.09 and R.12.
- SLICE-R.15: depends on R.08 and R.13.
- SLICE-R.16: depends on R.15.
- SLICE-R.17: depends on R.12, R.14, and R.15.
- SLICE-R.18: depends on R.14 and R.17.
- SLICE-R.19: depends on R.18 where protected auth path is needed.
- SLICE-R.20: depends on R.19.
- SLICE-R.21: depends on R.11 and on R.20 where tenant labels are referenced.
- SLICE-R.22: depends on R.18 and R.17.
- SLICE-R.23: depends on R.05 through R.22 contracts.
- SLICE-R.24: depends on at least R.02; can run parallel with later recovery
  once scratch path convention is fixed.
- SLICE-R.25: depends on R.02 and R.04.

## Citations

- Proposal and binding recovery contracts: `proposals/01-recovery-test-first.md`
  lines 451-1003 for slices, 1117-1128 for assumptions, 1151-1174 for Phase 5
  handoff, and 1179-1194 for required artifacts.
- Crossplane RCA: `research/01-rca-crossplane-webhook-unreachable.md` documents
  ready Crossplane pod/service/listener, API-server proxy 502, kube-router
  rejection, and the live `allow-observability-scrape` isolation failure.
- Coverage audit: `research/02-coverage-audit-init-100-118.md` documents
  141 audited tests, CI deadness for service suites, DEAD runtime validators,
  CAPTURED contract pytests, harmful Buildkite step-list assertion, and harmful
  `tests/test_discord_cli.py`.
- Process audit: `plans/process-tree-audits/init-100-119-process-tree-audit.md`
  documents missing 6b output indexes, red/green gates, process-tree audits,
  and supported-surface risk artifacts for INIT-101..119.
- Risk gate watch signals: `risk/01-recovery-scope.md` B4 and B5 require R.25
  contract-derived authorship discipline and R.01 closed namespace enumeration.
- Supported surface: `risk/01-recovery-supported-surface.md` SS3, SS4, SS8,
  SS10 define local-first scope, adjacent webhook namespaces, cluster cadence,
  and Docker/testcontainers blocker behavior.
- NetworkPolicy walk: `gitops/channels/local/observability/networkpolicies/observability-networkpolicies.yaml`
  contains all 11 `allow-observability-scrape` entries; all other
  `gitops/channels/local/**/networkpolicy*.yaml`, `*networkpolicies*.yaml`,
  `security/restricted-default-deny.yaml`, and `security/dns-egress.yaml` files
  were checked for equivalent NetworkPolicy content.
- Service infrastructure: `services/api/pyproject.toml`,
  `services/api/tests/conftest.py`, `services/discord/pyproject.toml`,
  `services/discord/tests/conftest.py`, `services/web/package.json`,
  `services/web/playwright.config.ts`, and `services/web/vite.config.ts`.
- E2E framework: `.buildkite/e2e-fullstack.yml`,
  `infra/tests/e2e/run-fullstack.sh`, `infra/tests/e2e/lib/assertions.sh`,
  `infra/tests/e2e/lib/bringup.sh`, `infra/tests/e2e/lib/teardown.sh`, and
  `infra/tests/e2e/lib/playwright/*`.
