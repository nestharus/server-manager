# BL-013 problem map — public-intake channel-completeness tripwire

## Current channel layout

`gitops/channels/` currently has one materialized channel:

- `gitops/channels/local/`

There is no `gitops/channels/dev/` directory today. That matches BL-013's
blocker: remote channel application workload specs are not materialized yet.
`infra/channels/dev.yaml` has remote channel configuration and access-policy
fields, but its GitOps block is deliberately omitted until remote Flux wiring
is scoped. Separately, `policy/cedar/channels/dev/` already exists, but that is
not the same thing as a remote application GitOps channel.

The local channel is broad, not just application workload material:

- `applications/server-manager/` contains the API deployment, service,
  ingress, database/runtime secrets, migration job, public-intake seed job,
  and `public-intake-rate-limit.yaml`.
- `applications/web/` contains the web workload.
- `auth/pomerium/` contains Pomerium rendered manifests, config secret,
  base ingresses, and `public-intake-rate-limit.yaml`.
- `auth/opal-cedar/`, `ingress/kong/`, `tls/`, `infisical/`,
  `object-storage/`, `observability/`, and other platform directories sit
  beside the application surface.

The existing public-intake tests are local-only. They load
`gitops/channels/local/...`, assert the Kong plugin and public paths, assert
the seeded Cedar policy fixture, and inspect the local Pomerium config routes.
They do not look across channels.

## Public-intake substrate group

The public-intake surface is not one file. The pieces that must travel
together are:

- Server-manager API side Kong rate-limit manifest:
  `gitops/channels/local/applications/server-manager/public-intake-rate-limit.yaml`
  defines `KongPlugin/public-intake-rate-limit` in namespace
  `server-manager` with rate-limiting config `minute: 5`, `hour: 50`,
  `policy: local`, and an annotated `Ingress/server-manager-public-intake-api`.
- API public-ingress paths in that same file:
  `api.local.humility.local` routes `/api/v1/public/applications` and
  `/api/v1/public/chapters` to `server-manager-api:8000`, with
  `konghq.com/plugins: public-intake-rate-limit`.
- Web/Pomerium side Kong rate-limit manifest:
  `gitops/channels/local/auth/pomerium/public-intake-rate-limit.yaml`
  defines `Ingress/web-public-intake` in namespace `auth-system`, also
  annotated with `konghq.com/plugins: public-intake-rate-limit`.
- Web public-ingress paths in that Pomerium-side file:
  `web.local.humility.local` routes `/api/public/applications`,
  `/api/public/chapters`, and `/api/applications` to `pomerium-proxy:80`.
- Cedar public-intake policy:
  `policy/cedar/channels/local/services/server-manager-api/policies.json`
  includes `public-intake-allow` for
  `Public::"web-intake.local"` +
  `Action::"application:submit_public"` +
  `Resource::"server-manager-api:public-applications"`, and
  `public-intake-no-read` forbidding that public principal from
  `Action::"api:read"` on `Resource::"server-manager-api"`.
- Pomerium route block:
  `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
  renders `pomerium-config` with `routes:` for the web host. Public-intake
  requests rely on the web host catch-all route with
  `allow_public_unauthenticated_access: true`, routed to
  `server-manager-web.web.svc.cluster.local:8080`. Adjacent identity-bearing
  routes must continue to precede the catch-all.
- Existing non-public ingresses that must not accidentally carry the plugin:
  `gitops/channels/local/auth/pomerium/ingress.yaml` has the web catch-all and
  protected API ingress without the public-intake plugin, and
  `gitops/channels/local/applications/server-manager/api-ingress.yaml` has the
  general API catch-all without the plugin.

The smallest useful group for BL-013 is therefore:

1. Public-intake API workload ingress plus `KongPlugin`.
2. Public-intake web/Pomerium ingress bound to the same plugin.
3. Public-intake Cedar allow/forbid entries for the same channel.
4. Pomerium web route coverage that keeps public application requests
   reachable without officer auth while preserving protected route ordering.

## What "complete" means per channel

For `local`, complete means the current checked-in shape:

- The public-intake API paths are exposed on `api.local.humility.local`.
- The public-intake web paths are exposed on `web.local.humility.local`.
- Both API-side and web-side public paths are bound to
  `public-intake-rate-limit`.
- The public principal is channel-local:
  `Public::"web-intake.local"`.
- The Cedar bundle allows public application submit and denies generic API
  read for that public principal.
- Pomerium config contains a public web route that lets the browser application
  reach the web app, while protected web/API routes remain explicit and ordered
  before the public catch-all.

For a future remote channel such as `dev`, complete should mean the same
logical resources with channel-derived values:

- A materialized `gitops/channels/<channel>/applications/server-manager/`
  workload surface exists.
- If that workload ships public-intake-relevant application manifests, the
  channel also ships the matching public-intake API rate-limit manifest.
- The channel's `auth/pomerium/` manifests include the matching web-side
  public-intake rate-limit ingress.
- `policy/cedar/channels/<channel>/services/server-manager-api/policies.json`
  includes the public-intake allow/forbid pair for that channel's public
  principal.
- Hostnames derive from the channel, not from local. Based on current channel
  config, a remote channel should use the remote domain pattern, for example
  `api.<channel>.humility.gg` and `web.<channel>.humility.gg`, rather than
  `api.local.humility.local` / `web.local.humility.local`.
- TLS issuer and secret names should follow the remote channel conventions, but
  the tripwire does not need to validate every TLS detail to catch the BL-013
  failure mode.

The important definition is conditional: a remote channel does not fail merely
because it is absent or because only policy exists. It fails when a non-local
GitOps channel begins shipping public-intake-relevant application material
without the rest of the substrate group.

## Test design options

Option A: directory-presence trigger.

Walk `gitops/channels/<channel>/` for every channel except `local`. If
`applications/server-manager/` exists with any YAML resources, assert the whole
public-intake group exists.

This is very loud, but too broad. A remote channel could initially materialize
private-only API workload resources and still intentionally keep public intake
out of scope.

Option B: public-intake workload trigger.

Walk each non-local `gitops/channels/<channel>/applications/server-manager/`
and parse YAML documents. Trigger only when one of these public-intake signals
appears:

- An `Ingress` host/path exposing `/api/v1/public/applications`,
  `/api/v1/public/chapters`, `/api/public/applications`,
  `/api/public/chapters`, or `/api/applications`.
- A manifest named `public-intake-rate-limit.yaml`.
- A resource named `server-manager-public-intake-api`,
  `web-public-intake`, or `public-intake-rate-limit`.
- A kustomization resource entry that includes
  `public-intake-rate-limit.yaml`.

Once triggered, assert all group members are present:

- `gitops/channels/<channel>/applications/server-manager/public-intake-rate-limit.yaml`
  exists.
- That file contains one `KongPlugin/public-intake-rate-limit` and an
  `Ingress/server-manager-public-intake-api` annotated with
  `konghq.com/plugins: public-intake-rate-limit`.
- The API-side ingress covers the public application and public chapter paths
  on a non-local, channel-derived API host.
- `gitops/channels/<channel>/auth/pomerium/public-intake-rate-limit.yaml`
  exists.
- That file contains `Ingress/web-public-intake`, annotated with the same
  plugin, covering the web public application, chapter, and compatibility
  application paths on a non-local, channel-derived web host.
- `gitops/channels/<channel>/auth/pomerium/secrets-infisicalsecret.yaml`
  exists and its `pomerium-config` route block has public web routing without
  shadowing protected routes.
- `policy/cedar/channels/<channel>/services/server-manager-api/policies.json`
  exists and includes both the public submit permit and public read forbid for
  the channel's public principal.

This is the best fit for the tripwire because it catches partial public-intake
materialization without blocking unrelated remote application bootstrap.

Option C: rendered-kustomize trigger.

Run or inspect rendered channel output and assert the group after kustomize
composition. This gives stronger deployment fidelity, but it is heavier and
less useful before the remote channel's render toolchain exists. BL-013's
narrow slice only needs a static CI tripwire.

Smallest useful test:

- Add one Python infra test that enumerates non-local directories under
  `gitops/channels/`.
- Skip absent channels naturally by walking only existing directories.
- For each channel, parse relevant YAML files using the same `yaml.safe_load_all`
  pattern as `test_public_intake_rate_limit.py`.
- Detect public-intake materialization with Option B signals.
- If no signal exists, assert nothing.
- If a signal exists, produce one failure message listing every missing group
  member so CI explains the incomplete channel in one run.

This should be a tripwire, not a full remote deployment conformance suite.

## What the proposal must lock

The proposal must lock the trigger condition. The most defensible wording:

> For any non-local `gitops/channels/<channel>/` directory, once that channel
> ships public-intake-relevant server-manager application manifests, CI must
> require the complete public-intake substrate group for the same channel.

It must also lock these details:

- Absence of `gitops/channels/dev/` is valid and must not fail.
- `policy/cedar/channels/dev/` by itself is not remote application workload
  materialization and must not trigger the tripwire.
- Local remains the reference implementation but the test must not hard-code
  local hostnames as acceptable for remote channels.
- The group travels together: API-side Kong plugin/ingress, web-side
  Pomerium/Kong ingress, Cedar public allow/forbid, and Pomerium public route
  coverage.
- The test is static CI coverage only. It does not claim remote runtime apply,
  Flux readiness, DNS, certificate issuance, or browser e2e proof.
- Existing local tests remain local semantic coverage. The new test adds
  cross-channel completeness coverage rather than replacing them.

## Diff budget

Expected implementation budget after this problem map:

- One focused test file under `infra/tests/`, probably
  `test_public_intake_channel_tripwire.py`.
- No production code changes.
- No GitOps manifest changes unless the proposal chooses to add a tiny fixture
  under tests instead of relying only on the current tree.
- Reuse existing helper style from `test_public_intake_rate_limit.py` and
  `test_applicant_discord_pomerium.py`: `Path` constants, `yaml.safe_load_all`,
  small resource filters, explicit assertion messages.
- No shell validator changes unless risk review specifically asks for the
  check to run outside pytest.

PROBLEM_MAP_DONE: research/47-bl-013-tripwire-problem-map.md
