# BL-013 — Supported-surface risk gate

**Verdict:** LOW

BL-013 (`proposals/32-bl-013-channel-tripwire.md`) is a test-layer-only
slice that adds one new pytest module
(`infra/tests/test_public_intake_channel_tripwire.py`) which
enumerates non-`local` directories under `gitops/channels/`, parses
their YAML with `yaml.safe_load_all`, and — only when a non-local
channel begins shipping public-intake-relevant `applications/server-manager`
material — asserts the matching public-intake substrate group is
present (API-side `public-intake-rate-limit.yaml`, Pomerium-side
`public-intake-rate-limit.yaml`, Cedar `public-intake-allow` /
`public-intake-no-read` for `Public::"web-intake.<channel>"`, and
Pomerium config public-route coverage). Proposal §3 ("Unmodified
substrate") and §5 ("Anti-scope") explicitly forbid any change to
production API, Discord daemon, web, repository, service, migration,
policy generator, GitOps manifests, OPAL/Cedar bundle, Pomerium config,
Authentik blueprint, Kong ingress, or any existing channel's manifests.
The current local substrate is reference input only. Negative and
positive coverage uses synthetic `tmp_path` fixtures, not on-disk
mutations.

## Check results

### 1. No public API change — ✓ PASS

No changes to:

- `services/api/app/api/v1/endpoints/applications/public.py`,
  `.../public_uploads.py`, `.../chapters/public.py`, or any other
  public/protected API route module;
- `PublicApplicationSubmission` /
  `PublicApplicationSubmissionReceipt` / chapter / upload-url
  request/response contracts;
- public-intake auth chain (`verify_applicant_receipt`,
  `authorize_public_intake`);
- web client (`services/web/src/api/client.ts`) or any caller of the
  public/upload-url endpoints.

The slice is purely test-layer additive: it introduces one new pytest
file that *reads* GitOps and policy YAML/JSON and uses synthetic
`tmp_path` fixture roots for its negative/positive cases (proposal §3
"Substrate / New file" + §4 TG-2/TG-3). Static YAML/JSON inspection
plus a temp-directory fixture cannot alter routing, request shape, or
auth behavior. The assertions only fail CI if a future commit drifts
or partially materializes a non-local channel's public-intake substrate.

### 2. Test is read-only over gitops + policy + infra trees — ✓ PASS

| Surface | Pre | Post | Status |
|---|---|---|---|
| `gitops/channels/local/**` | current local substrate (`applications/server-manager/public-intake-rate-limit.yaml`, `auth/pomerium/public-intake-rate-limit.yaml`, `auth/pomerium/secrets-infisicalsecret.yaml`, etc.) | unchanged — proposal §1, §3, §5 forbid any modification; `local` is explicitly skipped as the reference channel covered by existing local tests (TG-1 acceptance) | ✓ |
| `gitops/channels/dev/` (absent today) | not present | not created — proposal §1 + §2 Q1 + TG-1 acceptance: "absent `gitops/channels/dev/` does not fail" | ✓ |
| `gitops/channels/<future>/**` | n/a | not modified — tripwire is a *reader* only; channel materialization is anti-scope (proposal §5) | ✓ |
| `policy/cedar/channels/dev/` (already exists today) | current contents | unchanged — proposal §2 Q1 + TG-1 acceptance: "existing `policy/cedar/channels/dev/` does not trigger the tripwire by itself" | ✓ |
| `policy/cedar/channels/local/**` | post-BL-012 set | unchanged — proposal §3 forbids policy-bundle mutation | ✓ |
| `infra/tests/conftest.py` | existing | unchanged — new test uses only `pathlib`, `yaml`, and `json` plus pytest's built-in `tmp_path` (no new conftest plumbing) | ✓ |
| `infra/tests/test_public_intake_rate_limit.py`, `test_public_intake_policy_fixture.py`, `test_public_intake_form_seed_manifest.py` | existing local-only coverage | unchanged — proposal §3 "Existing local tests remain the local semantic coverage" | ✓ |
| Validator scripts (`validate_*.sh`) | existing CLIs | unchanged — proposal §6 explicitly says "No shell validator changes" | ✓ |

The new test's filesystem footprint is exactly:

- **Reads only** from `gitops/channels/` (enumerated, parsed) and
  `policy/cedar/channels/<channel>/services/server-manager-api/policies.json`
  (parsed) for whatever non-local channels exist on disk;
- **Writes only** under `tmp_path` (pytest's per-test temp dir)
  for the synthetic negative/positive fixtures in TG-2 and TG-3.

Verified at audit time:

- `gitops/channels/` contains exactly `local/` (no `dev/`), matching
  proposal §1 and the TG-1 "absent `gitops/channels/dev/` does not
  fail" acceptance.
- `policy/cedar/channels/` contains `dev/` and `local/`, matching
  proposal §1 and the TG-1 "existing `policy/cedar/channels/dev/`
  does not trigger the tripwire by itself" acceptance.
- The reference `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  manifest exists on disk under that exact path, so the trigger-rule
  signals (file name, resource names, plugin annotation, public path
  set) are grounded in the actual local substrate.

The diff budget (proposal §6) caps the slice at one ~180-260-line
test file with no production code, no GitOps manifest changes, no
policy bundle changes, and no shell validator changes.

### 3. No env / migrations / Pomerium / Authentik changes — ✓ PASS

| Surface | Pre | Post | Status |
|---|---|---|---|
| Process / Settings env vars | unchanged | unchanged — proposal §3 "No production API, Discord daemon, web, service, repository, migration, or policy generator changes" | ✓ |
| Alembic / DB migrations | post-INIT-137 head | unchanged — test-only slice | ✓ |
| Pomerium routes / config / blueprint (`gitops/channels/local/auth/pomerium/**`) | post-INIT-137 set | unchanged — proposal §3 + §5 + §6; the test only *reads* `secrets-infisicalsecret.yaml` and `public-intake-rate-limit.yaml` for the future-channel case (under `tmp_path` for fixtures, on-disk only when a non-local channel materializes) | ✓ |
| Authentik blueprint | post-INIT-134 set | unchanged — not touched | ✓ |
| OPAL / Cedar bundle | post-BL-012 set | unchanged — not touched (test reads `policies.json` for future non-local channels only) | ✓ |
| Kong chart / ingress / KongPlugin | post-BL-014 pinned set | unchanged — not touched | ✓ |
| InfisicalSecret content | unchanged | unchanged — `secrets-infisicalsecret.yaml`'s `pomerium-config` is read for routing assertions only | ✓ |
| CI lanes (Buildkite pipeline, validate scripts) | existing | unchanged — proposal §5 "Do not add … live Pomerium/Kong smoke checks. This slice is a static CI tripwire only" | ✓ |
| Channel materialization (`gitops/channels/dev/` and beyond) | absent / partial | unchanged — proposal §5 "Do not implement `dev` channel materialization or BL-013's full remote-channel scope" | ✓ |

Proposal §5 anti-scope explicitly bars runtime apply, Flux
reconciliation, DNS, certificate issuance, external ingress, browser
e2e, and live Pomerium/Kong smoke checks. Proposal §3 "Substrate /
Unmodified substrate" reiterates: no production code, no GitOps
manifest changes, no changes to existing channel materialization. The
slice cannot introduce env/migration/Pomerium/Authentik footprint
because it ships no shell, manifest, schema, or service code.

### 4. Pytest collects in existing infra/tests/ lane — ✓ PASS

Verified at audit time:

- `infra/tests/` is the existing pytest collection root and already
  contains `conftest.py`, `test_public_intake_rate_limit.py`,
  `test_public_intake_policy_fixture.py`,
  `test_public_intake_form_seed_manifest.py`,
  `test_applicant_discord_pomerium.py`,
  `test_kong_ingress_contract.py`,
  `test_opal_manifest_authority.py`, and the rest of the static
  contract suite — the same lane the proposal targets.
- The new module name `test_public_intake_channel_tripwire.py`
  matches pytest's default discovery glob (`test_*.py`) and the
  directory's existing naming convention (`test_public_intake_*`).
- Proposal §3 "Substrate / New file" pins helper style to the
  repository's existing `yaml.safe_load_all` idiom (used today in
  `test_public_intake_rate_limit.py`, `test_applicant_discord_pomerium.py`,
  `test_observability_contract.py`, etc.). Verified via grep: ten+
  files under `infra/tests/` already use that loader.
- The slice introduces **no** new conftest, no new pytest marker,
  no new fixture infrastructure, no new collection lane. It uses
  pytest's built-in `tmp_path` for its synthetic-channel fixtures
  (proposal §3 "fixture helpers that can run the same tripwire
  logic against a temporary synthetic channel root for negative and
  positive tests"; TG-2 and TG-3 acceptance).
- Proposal §4 "Test plan / TG-1" specifies the invocation:
  `pytest infra/tests/test_public_intake_channel_tripwire.py`.
  This is the same lane that currently runs the local public-intake
  rate-limit and policy-fixture tests.

### Test failure mode is loud + actionable — ✓ PASS

Although not one of the four gate criteria, the proposal's failure
contract is worth noting because it is the contract that makes the
tripwire useful in practice:

- **TG-1 (current repo state)**: skips `local`, treats absent
  `gitops/channels/dev/` as valid, treats policy-only `dev` as
  non-triggering. Pass condition is empty (no triggered non-local
  channel today), which is exactly the desired baseline.
- **TG-2 (partial fake channel under `tmp_path`)**: triggers on any
  of the public-intake signals from §2 Q1 (path-set Ingress, named
  manifest `public-intake-rate-limit.yaml`, named resource
  `server-manager-public-intake-api` / `web-public-intake` /
  `public-intake-rate-limit`, or kustomization include of
  `public-intake-rate-limit.yaml`). Failure aggregates every missing
  group member into one assertion using the §2 Q4 message format
  (`public-intake channel tripwire failed for <channel>: missing <item>`
  / `…: invalid <item>: <detail>`).
- **TG-3 (complete fake channel under `tmp_path`)**: proves the
  tripwire is channel-derived. The fixture uses
  `Public::"web-intake.<fake-channel>"` (not `web-intake.local`) and
  `api.<fake-channel>.humility.gg` / `web.<fake-channel>.humility.gg`
  (not `*.local.humility.local`), per §2 Q2 and Q3.

The §2 Q4 failure-message format (`public-intake channel tripwire
failed for <channel>: missing <item>`) names both the channel and the
specific missing/invalid item, and §2 Q4 mandates aggregation — when
several group members are missing, one assertion explains the whole
incomplete substrate in one CI run rather than producing a sequence of
single-item failures that mask each other.

## Findings

None blocking. Three observations worth surfacing for implementation:

- **Tripwire is genuinely conditional, not directory-presence.** The
  research problem map (`research/47-bl-013-tripwire-problem-map.md`,
  "Test design options" → Option A vs B) explicitly rejects the
  directory-presence trigger because it would force a remote channel
  bootstrapping *private-only* server-manager material to also ship
  the public-intake substrate. Proposal §2 Q1 locks the conditional
  trigger (Option B). Implementer must keep this conditional shape:
  the four trigger signals (path-set Ingress, named manifest, named
  resource, or kustomization include) are the only things that arm
  the tripwire for a given channel.

- **`policy/cedar/channels/dev/` is not a trigger.** The policy
  channel exists today but there is no corresponding
  `gitops/channels/dev/` workload. Proposal §1 and TG-1 explicitly
  require this to remain a passing baseline. Implementer must
  iterate `gitops/channels/<channel>/`, not
  `policy/cedar/channels/<channel>/`, when arming the tripwire.

- **Channel-derived hostnames and principal name.** Proposal §2 Q2
  + Q3 require non-local channels to use
  `api.<channel>.humility.gg` / `web.<channel>.humility.gg` and
  `Public::"web-intake.<channel>"`. The test must reject local-only
  hosts (`api.local.humility.local`, `web.local.humility.local`) and
  the local principal (`Public::"web-intake.local"`) when seen in
  non-local substrate. TG-3's positive fixture proves this is
  channel-derived rather than copy-pasted from local.

## Verdict reasoning

LOW.

1. **Public API surface (gate 1)**: zero touches. Public submit,
   chapter, and upload-url routes plus their request/response
   contracts and auth chain are byte-identical. The slice modifies
   only test code that reads YAML/JSON and writes into pytest's
   `tmp_path`.
2. **Read-only over gitops + policy + infra trees (gate 2)**: the
   new test is a pure reader of existing on-disk manifests and a
   `tmp_path` writer for synthetic fixtures. `local` is skipped;
   absent `dev/` is valid; policy-only `dev` is not a trigger.
   Verified by inspection: `gitops/channels/` contains only `local`,
   `policy/cedar/channels/` contains `dev` and `local`. No existing
   manifest, policy, or test file is mutated.
3. **No env / migrations / Pomerium / Authentik changes (gate 3)**:
   anti-scope is unusually explicit (proposal §3 "Unmodified
   substrate" + §5 "Anti-scope" + §6 budget caps the slice at one
   ~180-260-line test file). The slice cannot introduce env,
   migration, Pomerium, or Authentik footprint because it ships no
   shell, no manifest, no schema, no service code.
4. **Pytest collection surface (gate 4)**: the new file
   `infra/tests/test_public_intake_channel_tripwire.py` lands under
   the existing `infra/tests/` collection root, follows the
   `test_*.py` naming glob, and uses only `pathlib`, `yaml`, `json`,
   and pytest's built-in `tmp_path`. No new conftest, marker, or
   fixture lane. The proposal's run command (`pytest
   infra/tests/test_public_intake_channel_tripwire.py`) collects in
   the same lane that already runs the local public-intake rate-limit
   and policy-fixture tests.

The slice has zero blocking findings against the four supported-surface
gate criteria. Implementation can proceed without a supported-surface
re-gate, provided the implementer:

- keeps all changes inside the single new file
  `infra/tests/test_public_intake_channel_tripwire.py` under
  `infra/tests/`;
- preserves the conditional Option B trigger (Q1 signals only — not
  directory presence) so absent `gitops/channels/dev/` and policy-only
  `policy/cedar/channels/dev/` remain valid baselines;
- derives channel-public principal as `Public::"web-intake.<channel>"`
  and rejects local-only hostnames in non-local substrate (Q2 + Q3);
- aggregates missing-item failures into one per-channel assertion
  using the Q4 message format;
- uses pytest's built-in `tmp_path` for the TG-2/TG-3 synthetic
  fixtures (no on-disk channel scaffolding);
- leaves every existing GitOps manifest, Cedar policy bundle,
  Pomerium config, Authentik blueprint, Kong manifest, validator
  script, and existing pytest module unmodified.

Verdict: **LOW**.

SUPPORTED_SURFACE_DONE: plans/risk/bl-013-supported-surface.md
