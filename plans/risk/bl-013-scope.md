# BL-013 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/32-bl-013-channel-tripwire.md`
- `research/47-bl-013-tripwire-problem-map.md`

## Findings

### 1. Only adds infra/tests/test_public_intake_channel_tripwire.py — PASS

Proposal §3 "New file" declares exactly one file in the change surface:
`infra/tests/test_public_intake_channel_tripwire.py`. The authorized
behavior is confined to that single new pytest module:

- enumerate non-`local` directories under `gitops/channels/`;
- parse YAML with the repository's existing `yaml.safe_load_all` style;
- detect public-intake relevance using the Q1 trigger rules;
- for triggered channels, assert the Q2 group items;
- provide fixture helpers driving the same tripwire logic against
  synthetic channel roots under `tmp_path` for TG-2 and TG-3.

§6 diff budget caps the file at "roughly 180-260 lines" and explicitly
forbids any other modified file: "No production code", "No GitOps
manifest changes", "No policy bundle changes", "No shell validator
changes", "No documentation update required beyond this proposal."

The change surface is therefore one new pytest module under
`infra/tests/`, with no spill into other test directories, fixtures, or
CI configuration.

### 2. No production code, no GitOps manifest changes — PASS

§3 "Unmodified substrate" forbids both surfaces explicitly:

- "No production API, Discord daemon, web, service, repository,
  migration, or policy generator changes."
- "No GitOps manifest changes."
- "No changes to existing channel materialization."

§5 anti-scope reinforces the GitOps half: "Do not modify any existing
channel's manifests. The current local substrate is reference input,
not a target for this proposal." The local substrate referenced as
input —
`gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`,
`gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`,
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`, and
`policy/cedar/channels/local/services/server-manager-api/policies.json` —
remains read-only reference for the existing local tests, not a target
for this slice. §6 repeats the prohibition: "No production code", "No
GitOps manifest changes", "No policy bundle changes."

No service code, Pomerium policy, Discord daemon code, migration files,
Cedar policy bundles, kustomize overlays, or rendered Helm output are
touched.

### 3. No new dependencies — PASS

Proposal §3 binds the implementation to "the repository's existing
`yaml.safe_load_all` style" and "fixture helpers that can run the same
tripwire logic against a temporary synthetic channel root". The research
§"Diff budget" reinforces the same toolchain: "Reuse existing helper
style from `test_public_intake_rate_limit.py` and
`test_applicant_discord_pomerium.py`: `Path` constants,
`yaml.safe_load_all`, small resource filters, explicit assertion
messages." Cedar policy parsing via `policies.json` requires only the
standard library `json` module, already part of the existing infra-test
toolchain.

§6 diff budget does not introduce any new Python package, Go module,
Node package, fixture YAML under `gitops/`, runner script, container
image, or CI lane. No `helm`, `kubectl`, `kustomize`, `cedar`, or
`pomerium` toolchain is required at test time. The TG-1 / TG-2 / TG-3
acceptance commands all reduce to a single
`pytest infra/tests/test_public_intake_channel_tripwire.py` invocation
with no cluster, fixture pods, Flux reconciliation, DNS lookup, or
external service.

### 4. Doesn't implement dev channel itself — PASS

§5 anti-scope is explicit: "Do not implement `dev` channel
materialization or BL-013's full remote-channel scope. The missing
remote GitOps channel remains the blocker; this proposal only makes
future partial public-intake materialization fail fast." The §1 problem
statement frames the slice as a static CI tripwire, not a
materialization step: "BL-013's risk is that a future non-local GitOps
channel begins shipping public-intake-relevant server-manager
application manifests while omitting one of the matching channel-local
substrate pieces."

The TG-1 acceptance criteria explicitly preserve the current
non-materialized state: "absent `gitops/channels/dev/` does not fail",
"existing `policy/cedar/channels/dev/` does not trigger the tripwire by
itself", and "if no non-local channel contains public-intake-relevant
`applications/server-manager` manifests, the repository-state test
passes." TG-2 and TG-3 exercise the trigger and the complete-group
assertion against synthetic channels under `tmp_path` rather than by
adding any real `gitops/channels/dev/` directory or any
`policy/cedar/channels/dev/services/server-manager-api/policies.json`
content.

§5 also forbids adjacent shortcuts that would amount to partial
materialization: "Do not add runtime apply, Flux reconciliation, DNS,
certificate issuance, external ingress, browser e2e, or live
Pomerium/Kong smoke checks. This slice is a static CI tripwire only."
And: "Do not introduce compatibility shims, alternate principal names,
feature flags, deprecated aliases, or dual support for local and
channel-derived public principals." The Q3 lock binding the public
principal to `Public::"web-intake.<channel>"` ensures the test does not
back-door a `dev` channel by accepting `Public::"web-intake.local"` for
non-local channels.

## Conclusion

The proposal stays within a single new pytest file under
`infra/tests/`, introduces no production code, GitOps manifest, or Cedar
policy bundle changes, defers all dev-channel materialization and
live-cluster smoke to follow-up work, and adds no new dependency or
toolchain. Each gate check passes against an explicit proposal section.
Scope risk is acceptable.

SCOPE_DONE: plans/risk/bl-013-scope.md
