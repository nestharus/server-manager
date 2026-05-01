# BL-012 — Supported-surface risk gate

**Verdict:** LOW

BL-012 (proposals/29-bl-012-public-entity-runtime-probe.md) is a
test-layer-only slice. It extends
`infra/tests/validate_access_policy_local.sh` with two additional
live OPAL `/v1/is_authorized` probes for the `Public::"web-intake.local"`
principal (`application:submit_public` Allow, `api:read` Deny), runs
them inside the *existing* `init-115-cedar` proof pod after the
existing policy-id hydration check, and adds/updates one pytest under
`infra/tests/` to assert those probe payloads remain present in the
validator script. Proposal §5 ("Anti-scope") and §3 ("Unmodified
substrate") explicitly forbid any change to production API, Discord
daemon, web, repository, service, migration, policy generator, GitOps
manifests, OPAL image, Helm values, Cedar schema configuration, or
policy bundle content. Every public surface that operators or other
infrastructure depends on is preserved verbatim.

## Check results

### 1. No public API change — ✓ PASS

No changes to:
- `services/api/app/api/v1/endpoints/applications/public.py` or any
  other API route module;
- `PublicApplicationSubmission` / `PublicApplicationSubmissionReceipt`
  contracts;
- `authorize_public_intake` (`services/api/app/services/authorization.py`)
  Cedar request shape;
- public-intake auth chain (`verify_applicant_receipt` +
  `authorize_public_intake`);
- public chapters endpoint or any other public route.

The proposal is a test-layer additive change. The `Public::` Cedar
principal already exists in production policy text
(`policy/cedar/channels/local/services/server-manager-api/policies.json:10-17`)
and is already exercised by `authorize_public_intake`. BL-012 only
adds a live OPAL probe that proves the existing principal still
decides as expected; it does not introduce, rename, or alter any
public surface.

### 2. Validator script remains operator-callable with same args — ✓ PASS

`validate_access_policy_local.sh` CLI signature today
(`infra/tests/validate_access_policy_local.sh:14-22`, `:71-95`):

- `--channel <local>` (default `local`);
- `--kubeconfig <PATH>` (default `~/.kube/humility-local.yaml`);
- `--static-only` (skips runtime proof);
- `-h` / `--help`.

Proposal §3 ("Modified files") describes the changes purely as
in-place additions inside the existing proof command:

- two new payload variables beside `allow_payload` / `deny_payload`
  (currently at `:191-192`);
- four new curl invocations to `http://opal-client:8180/v1/is_authorized`
  inside the existing `cedar_proof_command` (currently at `:193-231`);
- four new log lines mirroring the existing `allow=…` / `deny=…` /
  `allow_after_poll=…` / `deny_after_poll=…` shape;
- focused shell assertions for public submit Allow and public read
  Deny (mirroring the existing assertions at `:247-256`).

No flags are added, removed, or renamed. The `usage()` block is not
changed in spirit (proposal does not require it; if updated, the
update would be additive prose). The `--static-only` short-circuit
at `:178-182` remains static-only and is explicitly preserved per
proposal §2 Q1 ("`--static-only` remains static-only and does not
attempt to catch OPAL/Cedar runtime behavior"). The diff budget
caps total script churn at ~60 lines.

Operator invocation `bash infra/tests/validate_access_policy_local.sh
--kubeconfig ~/.kube/humility-local.yaml` is byte-identical pre and
post.

### 3. No env vars / migrations / GitOps / Pomerium / Authentik changes — ✓ PASS

| Surface | Pre | Post | Status |
|---|---|---|---|
| Process / Settings env vars | unchanged | unchanged — proposal §3 "Unmodified substrate" forbids any production code change | ✓ |
| Alembic / DB migrations | β-3 head | unchanged — test-only slice | ✓ |
| GitOps manifests (`gitops/channels/local/**`) | post-INIT-137 set | unchanged — proposal §3 "No GitOps manifest changes" | ✓ |
| OPAL Helm values / image (`gitops/channels/local/auth/opal-cedar/`) | INIT-115 set | unchanged — proposal §3 "No OPAL image, Helm values, or Cedar schema configuration changes" | ✓ |
| Cedar schema | none today | unchanged — proposal §5 "Do not add a Cedar schema file" | ✓ |
| Pomerium routes / auth blueprint | post-INIT-137 set | unchanged — not touched | ✓ |
| Authentik blueprint | post-INIT-134 set | unchanged — not touched | ✓ |
| Kong ingress / rate-limit plugins | post-INIT-135 / -137 set | unchanged — not touched | ✓ |
| Cedar policy bundle (`policies.json`) | contains the public permit/forbid at `:10-17` | unchanged — proposal §5 "Do not modify policy bundle content" | ✓ |
| Service identity bundle (`service-identities.json`) | unchanged | unchanged — proposal §3 "Public is not modeled as a service identity" preserved | ✓ |

Two new pod-internal env injections (`--env=PUBLIC_SUBMIT_PAYLOAD=…`,
`--env=PUBLIC_READ_PAYLOAD=…` or equivalent names) on the existing
`kubectl run init-115-cedar` invocation
(`infra/tests/validate_access_policy_local.sh:233-240`) are
proof-pod-internal shell environment, not deployment env, not
persisted env, not part of any ConfigMap / Secret / InfisicalSecret.
They live and die with the proof pod alongside the existing
`EXPECTED_POLICY_IDS` / `ALLOW_PAYLOAD` / `DENY_PAYLOAD` injections
and follow the same idiom.

### 4. Pytest guard runs in existing infra/tests/ pytest collection — ✓ PASS

Proposal §3 specifies one of two equivalent placements:

- **Option A (default)**: extend
  `infra/tests/test_public_intake_policy_fixture.py`. The existing
  test `test_access_policy_validator_remains_matrix_driven_for_public_intake`
  (`:101-113`) currently asserts the validator does *not* contain
  `application:submit_public` or `web-intake.local`. The proposal
  inverts this: replace those negative assertions with positive
  assertions that the validator *does* contain the two public probe
  payload literals plus the expected decision checks. The other
  three tests in the file (`:46-65`, `:68-83`, `:86-98`) are kept
  unchanged.
- **Option B (acceptable alternate)**: add
  `infra/tests/test_validate_access_policy_local_probes.py` with the
  same assertions, leaving `test_public_intake_policy_fixture.py`
  unchanged.

Both paths sit under `infra/tests/`, the same directory that pytest
already collects today (the file `test_public_intake_policy_fixture.py`
is already there and is already executed). No new conftest, no new
pytest marker, no new fixture infrastructure. The diff budget caps
total pytest churn at ~35 lines.

The inversion at lines 112-113 is the one place where existing test
text *changes meaning* rather than being purely additive. It is
internally consistent with the proposal (the validator now intentionally
hardcodes those payloads, so asserting their absence would actively
contradict the slice). The test file path, function-naming convention
(`test_…`), and risk annotation docstring style are preserved, so
pytest collection and CI risk-coverage scanners continue to pick up
the test transparently.

## Findings

None blocking. One observation worth surfacing for implementation:

- **Inversion of an existing fixture assertion (Option A path).**
  `infra/tests/test_public_intake_policy_fixture.py:101-113` currently
  asserts the validator omits `application:submit_public` and
  `web-intake.local`. The slice replaces that with a positive presence
  assertion. This is acknowledged in proposal §3
  ("Replace the existing assertion that the validator omits …") and
  is internally consistent — once the validator hardcodes the public
  probes, the negative assertion would be wrong. If implementers
  prefer to keep the existing test untouched, proposal §3
  ("Acceptable alternate test file") allows adding
  `test_validate_access_policy_local_probes.py` instead. Either path
  satisfies the supported-surface check; the choice is implementer's.

## Verdict reasoning

LOW.

1. **Public API surface (gate 1)**: zero touches. Public submit
   route, contract, error mapping, auth chain, and Cedar request
   shape are byte-identical. `Public::"web-intake.local"` already
   exists in production policy and is already evaluated at runtime;
   the slice only adds a live probe that proves the existing
   evaluation still works.
2. **Validator CLI surface (gate 2)**: zero flag changes. Operator
   invocation is byte-identical. `--static-only` posture is
   explicitly preserved per proposal §2 Q1. Script churn capped at
   ~60 lines and isolated inside the existing proof pod
   command.
3. **Cross-cutting infra surfaces (gate 3)**: zero env / migration /
   GitOps / Pomerium / Authentik / OPAL image / Cedar schema /
   policy bundle / Helm-values / Kong / InfisicalSecret edits.
   Anti-scope is unusually explicit for this slice (proposal §3
   "Unmodified substrate" + §5 "Anti-scope"). Two pod-internal
   `--env=` injections on the existing `init-115-cedar` proof pod
   follow the existing idiom (`EXPECTED_POLICY_IDS`, `ALLOW_PAYLOAD`,
   `DENY_PAYLOAD`) and have no persisted footprint.
4. **Pytest collection surface (gate 4)**: the guard sits under
   `infra/tests/` (Option A modifies an existing file, Option B
   adds a new file in the same directory). Pytest discovery, conftest,
   risk-annotation docstring style, and CI collection lane are
   preserved. The single inversion at
   `test_public_intake_policy_fixture.py:112-113` is internally
   consistent with the slice and is the necessary corollary of the
   validator now intentionally containing the public probe literals.

The slice has zero blocking findings against the four supported-surface
gate criteria. Implementation can proceed without a supported-surface
re-gate, provided the implementer:

- keeps validator CLI flags unchanged;
- keeps the new probes inside the existing `init-115-cedar` proof
  pod's `cedar_proof_command` rather than spawning a new pod;
- keeps the pytest guard under `infra/tests/` so it lands in the
  existing collection lane;
- keeps the policy bundle, GitOps manifests, OPAL Helm values,
  Cedar schema, Pomerium routes, Authentik blueprint, and Kong
  ingress untouched.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/bl-012-supported-surface.md
