# BL-012 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/29-bl-012-public-entity-runtime-probe.md`
- `research/42-bl-012-public-entity-problem-map.md`
- `infra/tests/validate_access_policy_local.sh`

## Findings

### 1. Modifies only validate_access_policy_local.sh + test_public_intake_policy_fixture.py — PASS

Proposal §3 ("Modified files") declares exactly two files in the change
surface:

- `infra/tests/validate_access_policy_local.sh` — adds two public payload
  variables beside the existing `allow_payload`/`deny_payload`, posts both to
  `http://opal-client:8180/v1/is_authorized` in the existing
  `init-115-cedar` proof pod after policy hydration, repeats both posts after
  the existing polling-interval sleep + second hydration check, prints named
  log lines, asserts exactly one public-submit-allow and one public-read-deny
  line, and checks `.decision == "Allow"` / `"Deny"` accordingly.
- `infra/tests/test_public_intake_policy_fixture.py` — replaces the
  existing assertion that the validator omits `application:submit_public` /
  `web-intake.local` with a guard that asserts the validator now contains
  the two public probe payloads. Existing matrix and policy-bundle fixture
  tests stay unchanged.

§3 "Acceptable alternate test file" permits substituting
`infra/tests/test_validate_access_policy_local_probes.py` for the fixture
test. This is a one-for-one swap of the pytest guard, not an additive file:
"add or update one small guard test" (§6 diff budget). Either way the
change surface remains one validator script plus one pytest guard file
inside `infra/tests/`.

§3 "Unmodified substrate" explicitly excludes "production API, Discord
daemon, web, repository, service, migration, or policy generator changes,"
"GitOps manifest changes," "OPAL image, Helm values, or Cedar schema
configuration changes," and "policy bundle content changes." §6 diff
budget caps the validator churn at ~60 lines and the pytest churn at
~35 lines, with "No production code," "No policy bundle changes," "No
GitOps manifest changes."

### 2. No Cedar schema file added — PASS

Anti-scope §5 first clause: "Do not add a Cedar schema file. This
repository has no schema today, and whether to introduce one is a
separate design decision with broader policy and entity modeling
consequences." §3 "Unmodified substrate" reiterates "No … Cedar schema
configuration changes."

The research at `research/42-bl-012-public-entity-problem-map.md:13-19`
confirms there is currently no Cedar schema file or OPAL schema-related
env/config in `policy/` or `gitops/channels/local/auth/opal-cedar/`, and
the proposal deliberately leaves that absence in place — the BL-012
detector is for the day a future OPAL/Cedar runtime starts enforcing one,
not for introducing one now.

### 3. No extension to other principals — PASS

Q4 locks: "keep this slice scoped to `Public`." Anti-scope §5: "Do not
extend this proposal's runtime probes to other principals. Tenant, User,
and Service coverage already exists through the current access,
tenant-isolation, and service-identity proof paths."

Q2 declines the broader matrix-runner approach (Option D in the problem
map) precisely because it would "broaden the diff, change failure output
for existing probes, and invite unrelated coverage decisions about service
identities." The two new payloads are both `Public::"web-intake.local"`
only:

- allow `Public::"web-intake.local"` for `Action::"application:submit_public"`
  on `Resource::"server-manager-api:public-applications"`;
- deny `Public::"web-intake.local"` from `Action::"api:read"` on
  `Resource::"server-manager-api"`.

`Tenant`, `TenantChannel`, `User`, and `Service` runtime coverage stays
on its existing paths (`validate_tenant_isolation_local.sh`, the existing
`User::` allow/deny in the validator at lines 191-256, and service
identity proof at line 259) and is not touched.

### 4. No OPAL/Cedar version bump — PASS

Anti-scope §5: "Do not change OPAL or Cedar versions. BL-012 is a
regression detector for future runtime behavior changes, not an upgrade
proposal." §3 "Unmodified substrate" forbids "OPAL image, Helm values,
or Cedar schema configuration changes."

§3 "Modified files" describes only payload variables, four curl
invocations, four log lines, and shell assertions inside the existing
proof pod that already runs at `curlimages/curl:8.19.0` (validator
line 236). No `gitops/channels/local/auth/opal-cedar/` Helm values,
image tags, or `OPAL_POLICY_STORE_TYPE` knobs are touched.

### 5. No policy bundle changes — PASS

Anti-scope §5: "Do not modify policy bundle content. The public permit
and forbid statements already exist in
`policy/cedar/channels/local/services/server-manager-api/policies.json`;
the gap is runtime proof, not policy text." §3 "Unmodified substrate":
"No policy bundle content changes." §6 diff budget: "No policy bundle
changes."

The probes deliberately exercise the existing policy entries, which the
problem map locates at `policy/cedar/channels/local/services/server-manager-api/policies.json:10-17`
and which `test_public_intake_policy_fixture.py:68-83` already pins as
present. The validator additions do not modify, regenerate, or reseed
that bundle; they only post to `/v1/is_authorized` after the existing
`/v1/policies` hydration check confirms the canonical IDs are loaded.

## Conclusion

The proposal stays within the declared two-file change surface
(`infra/tests/validate_access_policy_local.sh` + one pytest guard under
`infra/tests/`), introduces no Cedar schema file, scopes the new runtime
probes strictly to the `Public` principal, leaves OPAL and Cedar versions
and Helm values untouched, and modifies no policy bundle content. Each
gate check passes against an explicit proposal section. Scope risk is
acceptable.

SCOPE_DONE: plans/risk/bl-012-scope.md
