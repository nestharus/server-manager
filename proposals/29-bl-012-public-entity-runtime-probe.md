# Proposal 29 - BL-012: Public entity runtime probe

## 1. Problem statement

`authorize_public_intake` builds the Cedar principal as
`Public::"web-intake.{channel}"`, using `local` as the fallback channel
(`services/api/app/services/authorization.py:24-31`). The local policy bundle
then permits `Public::"web-intake.local"` for public application submission and
forbids that same principal from `api:read`
(`policy/cedar/channels/local/services/server-manager-api/policies.json:10-17`).

The risk is not current policy drift. The risk is a future OPAL/Cedar runtime
that starts enforcing a Cedar schema or a fixed entity type registry while this
repo still ships only policy statements. There is no Cedar schema file or
OPAL schema-related env/config in the current policy or local OPAL/Cedar
manifests. The local OPAL client is configured as a Cedar store and the server
loads generated Cedar policy files from the seeded git repo.

If strict schema enforcement appears and does not include a `Public` principal
type, the public-intake authorization chain can fail even though the policy
fixture still contains the intended statements. Depending on where enforcement
lands, failures could appear as policy hydration/bootstrap failure, an OPAL
`/v1/is_authorized` error, or an API-side 503/403 for all public submits.

Existing static tests already prove the public-intake policy text and access
matrix entries remain present. The missing coverage is a live OPAL/Cedar
decision probe for `Public::"web-intake.local"`.

## 2. Decisions

### Q1. Test shape

Lock: use the problem map's Option B/D hybrid.

Extend `infra/tests/validate_access_policy_local.sh` with two live OPAL probes
for the public principal:

- allow `Public::"web-intake.local"` to perform
  `Action::"application:submit_public"` on
  `Resource::"server-manager-api:public-applications"`;
- deny `Public::"web-intake.local"` from performing `Action::"api:read"` on
  `Resource::"server-manager-api"`.

Also add a Python guard test under `infra/tests/` that reads the validator
script and asserts both public probe payloads are present. This keeps the
runtime check from being removed while the static policy fixture tests still
pass.

The live probes must run only after `/v1/policies` confirms the canonical OPAL
policy IDs are hydrated, using the same runtime lane as the current access
policy validator. `--static-only` remains static-only and does not attempt to
catch OPAL/Cedar runtime behavior.

### Q2. Probe payload source

Lock: hardcode the two public probe payloads in
`validate_access_policy_local.sh`, then guard their presence in pytest.

The stronger long-term pattern is a matrix runner derived from
`infra/tests/fixtures/contracts/access_policy_matrix.yml`, but that is larger
than this BL-012 slice because the existing validator has hand-written runtime
payloads and shell-side assertions for only the sample `User::` allow/deny
case. Converting the script into a general YAML matrix runner would broaden the
diff, change failure output for existing probes, and invite unrelated coverage
decisions about service identities.

For this proposal, the contract matrix remains the source of static intended
decisions, and the validator gets the minimum live coverage that closes the
`Public::` runtime gap. The pytest guard should assert exact validator content
for:

- `Public::\"web-intake.local\"`;
- `Action::\"application:submit_public\"`;
- `Resource::\"server-manager-api:public-applications\"`;
- the public read-deny payload using `Action::\"api:read\"` and
  `Resource::\"server-manager-api\"`.

### Q3. Failure signal wording

Lock: failure messages must name the public principal, action, expected
decision, and observed OPAL response.

Operator-facing failures should use this shape:

```text
Cedar public submit runtime probe expected Allow for Public::"web-intake.local" application:submit_public, got: <body>
Cedar public read runtime probe expected Deny for Public::"web-intake.local" api:read, got: <body>
```

If OPAL policy hydration fails before the probes run, keep the existing
hydration failure path that reports missing policy IDs and the last
`/v1/policies` body. That already catches bootstrap-time rejection of the
bundle containing the public policies. The new probe wording is for
decision-time rejection or wrong decisions after hydration succeeds.

The validator should also keep cardinality checks, so duplicate or missing
public probe log lines fail clearly:

```text
expected exactly one Cedar public submit Allow log line, found <n>
expected exactly one Cedar public read Deny log line, found <n>
```

### Q4. Scope of other principals

Lock: keep this slice scoped to `Public`.

`Tenant` and `TenantChannel` have their own live OPAL validator path in
`infra/tests/validate_tenant_isolation_local.sh` plus a static guard that keeps
those probes present. `User` and baseline `Resource`/`Action` behavior are
already exercised by the current access policy validator. `Service` identities
are covered through service identity claim/runtime proof paths and static
contract checks.

Do not expand BL-012 to a full runtime matrix runner for `Tenant`, `User`, or
`Service`. That may be a useful follow-up, but the uncovered production risk in
this slice is public submit failing because OPAL/Cedar stops accepting the
`Public` principal type.

## 3. Substrate

### Modified files

- `infra/tests/validate_access_policy_local.sh`
  - Add two public payload variables beside the existing `allow_payload` and
    `deny_payload`.
  - Post both payloads to `http://opal-client:8180/v1/is_authorized` in the
    existing proof pod after initial policy hydration.
  - Repeat both posts after the existing polling-interval sleep and second
    policy hydration check.
  - Print named log lines for the public submit and public read probes.
  - Assert exactly one public submit allow line and one public read deny line.
  - Assert `.decision == "Allow"` for public submit and `.decision == "Deny"`
    for public read.

- `infra/tests/test_public_intake_policy_fixture.py`
  - Replace the existing assertion that the validator omits
    `application:submit_public` and `web-intake.local` with a guard that asserts
    the validator contains the two live public probe payloads.
  - Keep the existing matrix and policy-bundle fixture tests unchanged.

### Acceptable alternate test file

If keeping validator-implementation guards separate reads cleaner, add
`infra/tests/test_validate_access_policy_local_probes.py` instead of extending
`test_public_intake_policy_fixture.py`. The required assertions are the same:
the validator must contain both public probe payloads and expected decision
checks.

### Unmodified substrate

- No production API, Discord daemon, web, repository, service, migration, or
  policy generator changes.
- No GitOps manifest changes.
- No OPAL image, Helm values, or Cedar schema configuration changes.
- No policy bundle content changes.

## 4. Test plan

### TG-1: live OPAL public probes pass

Run the existing validator against a local OPAL/Cedar runtime with canonical
policies loaded:

```bash
bash infra/tests/validate_access_policy_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

Acceptance:

- `/v1/policies` hydrates all canonical policy IDs, including the policies that
  contain the public permit and forbid statements.
- the public submit payload returns exactly one OPAL response with
  `.decision == "Allow"`;
- the public read payload returns exactly one OPAL response with
  `.decision == "Deny"`;
- both public probes pass before and after the existing polling-interval
  recheck;
- the script exits zero and prints a `RESULT: pass=... fail=0 skip=...`
  summary.

### TG-2: pytest guard proves the runtime probes exist

Run the public-intake fixture tests:

```bash
pytest infra/tests/test_public_intake_policy_fixture.py
```

If the guard is split into a new file, include that file in the pytest command.

Acceptance:

- the matrix still contains the public submit allow and public read deny cases;
- the canonical policy bundle still contains the matching permit and forbid;
- no service identity is introduced for public intake;
- the validator script contains the public submit and public read live probe
  payloads and expected decision checks.

## 5. Anti-scope

Do not add a Cedar schema file. This repository has no schema today, and
whether to introduce one is a separate design decision with broader policy and
entity modeling consequences.

Do not extend this proposal's runtime probes to other principals. Tenant,
User, and Service coverage already exists through the current access,
tenant-isolation, and service-identity proof paths.

Do not change OPAL or Cedar versions. BL-012 is a regression detector for
future runtime behavior changes, not an upgrade proposal.

Do not modify policy bundle content. The public permit and forbid statements
already exist in
`policy/cedar/channels/local/services/server-manager-api/policies.json`; the
gap is runtime proof, not policy text.

Do not convert the validator into a full matrix runner in this slice. That is
larger than needed to close BL-012 and should be proposed separately if wanted.

## 6. Diff budget

Expected implementation size: two confined test-layer changes.

Budget:

- `infra/tests/validate_access_policy_local.sh`: add two payload variables,
  four curl invocations inside the proof command, four log lines, and focused
  shell assertions for public submit/public read decisions. Keep total script
  churn under roughly 60 lines.
- `infra/tests/test_public_intake_policy_fixture.py` or
  `infra/tests/test_validate_access_policy_local_probes.py`: add or update one
  small guard test. Keep total pytest churn under roughly 35 lines.
- No production code.
- No policy bundle changes.
- No GitOps manifest changes.
- No documentation update required beyond this proposal.

PROPOSAL_DONE: proposals/29-bl-012-public-entity-runtime-probe.md
