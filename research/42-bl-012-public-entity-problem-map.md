# BL-012 problem map — Public:: entity acceptance

## What's at risk

`authorize_public_intake` builds the Cedar principal as
`Public::"web-intake.{channel}"`, using `local` as the fallback channel
(`services/api/app/services/authorization.py:24-31`). The local policy bundle
then permits `Public::"web-intake.local"` for public application submission and
forbids that same principal from `api:read`
(`policy/cedar/channels/local/services/server-manager-api/policies.json:10-17`).

The risk is not current policy drift. The risk is a future OPAL/Cedar runtime
that starts enforcing a Cedar schema or a fixed entity type registry while this
repo still ships only policy statements. I found no Cedar schema file or OPAL
schema-related env/config in `policy/`, `gitops/channels/local/auth/opal-cedar/`,
or the access/tenant validators. The local OPAL client is configured as a Cedar
store (`OPAL_POLICY_STORE_TYPE=CEDAR`) and the server loads `.cedar` policy
files from the seeded git repo (`gitops/channels/local/auth/opal-cedar/render-values.yaml:5-9`,
`:23-29`).

If strict schema enforcement appears and does not include a `Public` principal
type, the public-intake authorization chain can fail even though the policy
fixture still contains the intended statements. Depending on where enforcement
lands, failures could appear as policy hydration/bootstrap failure, an OPAL
`/v1/is_authorized` error, or an API-side 503/403 for all public submits.

## Existing test coverage

Every current public-intake authorization test I found:

- `infra/tests/fixtures/contracts/access_policy_matrix.yml:10-17` includes the
  `Public::"web-intake.local"` allow case for
  `Action::"application:submit_public"` and deny case for `Action::"api:read"`.
- `infra/tests/test_public_intake_policy_fixture.py:46-65` asserts those two
  matrix cases remain present.
- `infra/tests/test_public_intake_policy_fixture.py:68-83` asserts the local
  `policies.json` bundle contains matching permit/forbid statements.
- `infra/tests/test_public_intake_policy_fixture.py:86-98` asserts public intake
  did not get modeled as a service identity.
- `infra/tests/test_public_intake_policy_fixture.py:101-113` asserts
  `validate_access_policy_local.sh` remains matrix-driven and does not hard-code
  `application:submit_public` or `web-intake.local`.
- `infra/tests/test_access_policy_contract.py:66-112` loops over all access
  matrix decisions, so it also checks that the public allow/deny matrix entries
  match the policy fixture. This is syntax/text-level fixture coverage, not live
  OPAL behavior.
- `infra/tests/test_access_policy_contract.py:115-123` and
  `infra/tests/test_cedar_seeded_source_equality.py` prove the seeded `.cedar`
  policy files equal canonical `policies.json`, which indirectly preserves the
  public policies in OPAL's source repo.
- `services/api/tests/test_public_application_route.py:218-224` asserts the API
  route sends the expected public Cedar request to a fake authorizer.
- `services/api/tests/test_public_application_route.py:227-251` asserts a fake
  Cedar deny maps to `403 public_intake_forbidden`.
- `infra/tests/test_public_intake_rate_limit.py:71-116` covers Kong rate-limit
  binding for public submit paths. It protects abuse posture, not Cedar entity
  acceptance.

The live runtime validators currently cover OPAL hydration and authorization,
but not `Public::`. `infra/tests/validate_access_policy_local.sh:187-260`
waits for OPAL policy IDs, probes a sample `User::` allow and `User::` deny,
waits one polling interval, then repeats those probes. Tenant coverage separately
probes `Tenant::"sample"` and `TenantChannel::*` in
`infra/tests/validate_tenant_isolation_local.sh`, with a static guard in
`infra/tests/test_tenant_policy_source_contract.py:30-43`.

One path mismatch: the prompt names `gitops/channels/local/auth/opal/`, but this
worktree has `gitops/channels/local/auth/opal-cedar/`.

## Failure boundaries

- Static fixture boundary: current tests would catch removal or text drift of
  the `Public::"web-intake.local"` policy entries. They would not catch a future
  OPAL/Cedar release rejecting the entity type at policy load or authorization
  time.
- Seeded-source boundary: seeded `.cedar` equality tests would catch generator
  drift. They would not catch OPAL interpreting the same Cedar text differently.
- OPAL hydration boundary: if future OPAL/Cedar rejects a policy file containing
  `Public::`, `/v1/policies` may never show the expected policy IDs. Existing
  runtime validators would fail only because the complete policy-id set cannot
  hydrate, not because they intentionally probe the public principal.
- OPAL decision boundary: if policies hydrate but `/v1/is_authorized` rejects an
  unknown principal type at decision time, existing live access tests would miss
  it because they probe only `User::` in the access validator and `Tenant::` in
  the tenant validator.
- API runtime boundary: if CI misses the runtime rejection, public submit hits
  `authorize_public_intake`; `CedarAuthorizationUnavailableError` maps to 503,
  while a non-Allow decision maps to 403
  (`services/api/app/services/authorization.py:33-39`).

## Test design options

Option A: pure unit test asserting policy file syntax.

This is already covered by `test_public_intake_policy_fixture.py` and the broader
access matrix contract. It is cheap and should stay, but it cannot catch OPAL or
Cedar schema enforcement because it never runs the OPAL Cedar store.

Option B: live OPAL container test that loads our policy bundle.

This is the smallest test that catches the BL-012 risk. The current runtime
validator already waits for live OPAL hydration and posts to `/v1/is_authorized`;
it should add public payloads for:

```json
{"principal":"Public::\"web-intake.local\"","action":"Action::\"application:submit_public\"","resource":"Resource::\"server-manager-api:public-applications\""}
{"principal":"Public::\"web-intake.local\"","action":"Action::\"api:read\"","resource":"Resource::\"server-manager-api\""}
```

Expected decisions: Allow, Deny. The strongest shape is to derive those payloads
from `infra/tests/fixtures/contracts/access_policy_matrix.yml`, or at minimum
add the two public probes beside the existing `ALLOW_PAYLOAD`/`DENY_PAYLOAD` in
`infra/tests/validate_access_policy_local.sh`. This catches both bootstrap
rejection and decision-time rejection before the API route is exercised by real
public traffic.

Option C: contract test against a pinned OPAL/Cedar schema-validation feature
flag if/when it exists.

There is no such config in the current manifests. If OPAL/Cedar later exposes an
explicit schema-validation flag, a contract test should pin it deliberately and
assert `Public` is represented in the schema or the feature remains disabled by
decision. This is a future hardening test, not the current smallest fix.

Option D: include `Public::` in the broader Cedar policy fixture matrix.

The public principal is already in the fixture matrix. The missing piece is that
the runtime validator does not execute the full matrix. Turning
`validate_access_policy_local.sh` into a matrix runner would be slightly larger
than adding two payloads, but it is the better general pattern: any future
principal/resource entity type added to the matrix would automatically get a
live OPAL authorization probe.

## Other untyped principals at risk

There is no registered Cedar schema in this repo, so every Cedar entity literal
in `policy/` is technically untyped from Cedar's perspective. The local policy
bundle contains these entity types:

- Principals: `User`, `Service`, `Public`, `Tenant`.
- Resources: `Resource`, `TenantChannel`.
- Actions: `Action`.

Risk ranking:

- `Public` is the uncovered BL-012 gap. It appears only in the local policy
  bundle and access matrix, not in service identities, channel JSON schema, or a
  live OPAL public decision probe.
- `Tenant` and `TenantChannel` have similar schema-enforcement exposure, but
  they already have a live validator path that probes allow/allow/deny decisions
  through OPAL (`infra/tests/validate_tenant_isolation_local.sh`) and a static
  test that ensures those probes remain present
  (`infra/tests/test_tenant_policy_source_contract.py:30-43`).
- `Service` is constrained by the platform-channel JSON schema to
  `Service::"..."` principals for service identities, and service identity
  runtime proof exercises machine principals.
- `User`, `Resource`, and `Action` are baseline entity types used by the
  original access policy proof. The access validator probes `User::` and
  `Resource::` through OPAL, but only for the protected API read action.

The best combined coverage is not a one-off Public-only static test. It is a
runtime matrix probe that includes `Public`, `User`, `Service`, and tenant cases,
or at least adds the public allow/deny pair to the existing live access validator
now and records matrix execution as the follow-up generalization.

## What the proposal must lock

- Test location: extend `infra/tests/validate_access_policy_local.sh` for the
  live OPAL proof, and add/update a Python guard under `infra/tests/` so the
  validator cannot silently drop the public probes.
- Test mechanism: post the public submit allow and public read deny payloads to
  `http://opal-client:8180/v1/is_authorized` only after `/v1/policies` confirms
  the canonical policy IDs are hydrated.
- When it runs: in the same runtime CI/e2e lane that runs the existing access
  policy validator against OPAL/Cedar. `--static-only` cannot catch this class of
  OPAL/Cedar behavior change.
- Contract source: keep `infra/tests/fixtures/contracts/access_policy_matrix.yml`
  as the source of intended decisions if the diff budget allows; otherwise lock
  the two public payloads explicitly and guard their presence in a small pytest.
- Failure signal: fail CI if public submit is not `Allow`, if public read is not
  `Deny`, or if OPAL cannot hydrate the policy set containing the public
  policies.

## Diff budget

Small. Expected implementation should be limited to:

- `infra/tests/validate_access_policy_local.sh`: add two public payloads, execute
  them before and after the polling-interval recheck, and assert exactly one
  public allow and one public deny decision.
- One pytest guard, likely in `infra/tests/test_public_intake_policy_fixture.py`
  or `infra/tests/test_access_policy_runtime_gate.py`, asserting the validator
  contains `Public::\"web-intake.local\"` and
  `Action::\"application:submit_public\"` in the live proof block.
- No production API changes, no policy text changes, no OPAL manifest changes
  unless proposal research finds an explicit schema-validation flag that must be
  pinned.

PROBLEM_MAP_DONE: research/42-bl-012-public-entity-problem-map.md
