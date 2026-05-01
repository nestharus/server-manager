# Proposal 32 - BL-013: Public-intake channel tripwire

## 1. Problem statement

`gitops/channels/` currently has one materialized application GitOps channel:
`gitops/channels/local/`. There is no `gitops/channels/dev/` directory today.
That absence is valid and must not fail CI. Separately,
`policy/cedar/channels/dev/` already exists, but policy materialization alone
is not remote application workload materialization and must not trigger this
tripwire.

The current public-intake substrate is local-only and consists of a group of
resources that must travel together:

- API-side Kong rate-limit manifest and public-only Ingress:
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`.
- Web/Pomerium-side public-only Ingress:
  `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`.
- Cedar public submit permit and generic API read forbid:
  `policy/cedar/channels/local/services/server-manager-api/policies.json`.
- Pomerium route coverage in
  `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`.

Existing tests prove the local substrate shape. They do not look across
channels. BL-013's risk is that a future non-local GitOps channel begins
shipping public-intake-relevant server-manager application manifests while
omitting one of the matching channel-local substrate pieces. That would make a
remote public intake surface partially materialized: public routes, rate
limits, authorization policy, or Pomerium routing could drift independently.

For any non-local `gitops/channels/<channel>/` directory, once that channel
ships public-intake-relevant server-manager application manifests, CI must
require the complete public-intake substrate group for the same channel.

## 2. Decisions

### Q1. Trigger detection

Lock: trigger on public-intake-relevant server-manager application manifests,
not on channel directory existence alone.

For every non-local directory under `gitops/channels/`, inspect
`gitops/channels/<channel>/applications/server-manager/` if it exists. The
tripwire is armed for that channel when the directory contains non-empty YAML
that signals public intake in any of these ways:

- an `Ingress` host/path exposing `/api/v1/public/applications`,
  `/api/v1/public/chapters`, `/api/public/applications`,
  `/api/public/chapters`, or `/api/applications`;
- a YAML file named `public-intake-rate-limit.yaml`;
- a resource named `server-manager-public-intake-api`,
  `web-public-intake`, or `public-intake-rate-limit`;
- a `Kustomization` resource entry that includes
  `public-intake-rate-limit.yaml`.

This keeps absent remote channels valid and avoids failing private-only remote
bootstrap. It also avoids the opposite shortcut: if a remote channel starts
shipping any public-intake-specific material, the rest of the group becomes
mandatory immediately.

### Q2. Required group items per channel

Lock: once triggered, the channel must contain all four substrate items below.

1. API-side KongPlugin and public-only Ingress:
   `gitops/channels/<channel>/applications/server-manager/public-intake-rate-limit.yaml`
   must exist. It must contain `KongPlugin/public-intake-rate-limit` and
   `Ingress/server-manager-public-intake-api`. The Ingress must use
   `konghq.com/plugins: public-intake-rate-limit` and must expose
   `/api/v1/public/applications` and `/api/v1/public/chapters` as
   path-specific `Prefix` routes to `server-manager-api:8000`.

2. Web-side Pomerium/Kong public-only Ingress:
   `gitops/channels/<channel>/auth/pomerium/public-intake-rate-limit.yaml`
   must exist. It must contain `Ingress/web-public-intake` with
   `konghq.com/plugins: public-intake-rate-limit` and must expose
   `/api/public/applications`, `/api/public/chapters`, and legacy
   `/api/applications` as path-specific `Prefix` routes to
   `pomerium-proxy:80`.

3. Cedar public principal policy:
   `policy/cedar/channels/<channel>/services/server-manager-api/policies.json`
   must exist. It must include:
   - `public-intake-allow` permitting the channel public principal to perform
     `Action::"application:submit_public"` on
     `Resource::"server-manager-api:public-applications"`;
   - `public-intake-no-read` forbidding the same principal from
     `Action::"api:read"` on `Resource::"server-manager-api"`.

4. Pomerium route coverage:
   `gitops/channels/<channel>/auth/pomerium/secrets-infisicalsecret.yaml` must
   exist. Its `pomerium-config` rendered `config.yaml` must include web-host
   routing that lets public application requests reach
   `server-manager-web.web.svc.cluster.local:8080` with
   `allow_public_unauthenticated_access: true`. Identity-bearing web/API
   routes for the same web host must remain explicit and ordered before the
   public catch-all so protected paths are not shadowed.

For non-local channels, hostnames must be channel-derived rather than copied
from local. The tripwire should reject local-only hosts such as
`api.local.humility.local` or `web.local.humility.local` in non-local substrate.
The expected remote hostname pattern for this check is
`api.<channel>.humility.gg` and `web.<channel>.humility.gg`.

### Q3. Channel principal name

Lock: derive the public principal from the channel name:

```text
Public::"web-intake.<channel>"
```

The test must not hard-code `Public::"web-intake.local"` as acceptable for
non-local channels. For example, a future `dev` channel must require
`Public::"web-intake.dev"` in both the submit permit and read forbid policies.

### Q4. Failure message format

Lock: every failure must name the channel and the missing or invalid item.

Use messages with this shape:

```text
public-intake channel tripwire failed for <channel>: missing <item>
public-intake channel tripwire failed for <channel>: invalid <item>: <detail>
```

When several group members are missing, aggregate them into one assertion for
the channel so CI explains the incomplete substrate in one run.

## 3. Substrate

### New file

- `infra/tests/test_public_intake_channel_tripwire.py`
  - Enumerate directories under `gitops/channels/`, excluding `local`.
  - Parse YAML using the repository's existing `yaml.safe_load_all` style.
  - Detect public-intake relevance from the trigger rules in Q1.
  - For triggered channels, assert the group items from Q2.
  - Provide fixture helpers that can run the same tripwire logic against a
    temporary synthetic channel root for negative and positive tests.

### Unmodified substrate

- No production API, Discord daemon, web, service, repository, migration, or
  policy generator changes.
- No GitOps manifest changes.
- No changes to existing channel materialization.
- Existing local tests remain the local semantic coverage. The new test adds
  cross-channel completeness coverage.

## 4. Test plan

### TG-1: current repository passes

Run:

```bash
pytest infra/tests/test_public_intake_channel_tripwire.py
```

Acceptance:

- `local` is skipped as the reference channel already covered by local tests;
- absent `gitops/channels/dev/` does not fail;
- existing `policy/cedar/channels/dev/` does not trigger the tripwire by
  itself;
- if no non-local channel contains public-intake-relevant
  `applications/server-manager` manifests, the repository-state test passes.

### TG-2: partial fake channel fails

In the new pytest file, synthesize a fake non-local channel under `tmp_path`
with public-intake-relevant `applications/server-manager` material and only
part of the substrate group.

Acceptance:

- the tripwire detects the fake channel as public-intake-relevant;
- the assertion fails;
- the failure text names the fake channel and every missing item, using the
  format locked in Q4.

### TG-3: complete fake channel passes

In the same pytest file, synthesize a fake non-local channel under `tmp_path`
with the full substrate group:

- API-side `public-intake-rate-limit.yaml`;
- Pomerium-side `public-intake-rate-limit.yaml`;
- Cedar policies using `Public::"web-intake.<fake-channel>"`;
- Pomerium config routes covering the public web paths.

Acceptance:

- the tripwire detects the fake channel as public-intake-relevant;
- all required group checks pass;
- the fixture proves the test is channel-derived and does not rely on
  `web-intake.local` or local hostnames.

## 5. Anti-scope

Do not add runtime apply, Flux reconciliation, DNS, certificate issuance,
external ingress, browser e2e, or live Pomerium/Kong smoke checks. This slice
is a static CI tripwire only.

Do not modify any existing channel's manifests. The current local substrate is
reference input, not a target for this proposal.

Do not implement `dev` channel materialization or BL-013's full remote-channel
scope. The missing remote GitOps channel remains the blocker; this proposal
only makes future partial public-intake materialization fail fast.

Do not introduce compatibility shims, alternate principal names, feature
flags, deprecated aliases, or dual support for local and channel-derived public
principals.

## 6. Diff budget

Expected implementation size: one confined test file.

Budget:

- `infra/tests/test_public_intake_channel_tripwire.py`: roughly 180-260 lines,
  including YAML/JSON loaders, small resource filters, channel-derived
  expected-value helpers, repository-state coverage, and two fixture-based
  tests.
- No production code.
- No GitOps manifest changes.
- No policy bundle changes.
- No shell validator changes.
- No documentation update required beyond this proposal.

PROPOSAL_DONE: proposals/32-bl-013-channel-tripwire.md
