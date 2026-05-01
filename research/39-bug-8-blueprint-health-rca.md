# RCA: BUG-8 Silent Authentik Blueprint Apply Failures

## Scope

This is root-cause analysis only. It documents why Authentik blueprint import
failures can pass through local cluster bootstrap, gitserver reseed, and the
current e2e suite without an early failure signal. It includes candidate
intervention points and tradeoffs, but does not select or prescribe a fix.

Sources used:

- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
- `gitops/channels/local/auth/authentik/render-values.yaml`
- `gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml`
- `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml`
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
- `infra/scripts/install-flux-for-channel.sh`
- `infra/scripts/bring-up-local-channel.sh`
- `infra/tests/test_applicant_discord_blueprint.py`
- Authentik 2026.2 blueprint docs:
  <https://docs.goauthentik.io/customize/blueprints>
- Authentik API reference for managed blueprint instances:
  <https://api.goauthentik.io/reference/managed-blueprints-retrieve/>

## Symptom + State

BUG-8 exposed a delayed-failure pattern:

1. A mounted Authentik blueprint failed during Authentik runtime apply.
2. Authentik recorded the blueprint instance as `status='error'` in
   `authentik_blueprints_blueprintinstance`.
3. Kubernetes objects still applied successfully, Authentik still reached
   pod readiness, and Flux still had no Kubernetes-level reason to fail.
4. Pomerium login still worked because the Pomerium provider existed with the
   default `openid`, `email`, and `profile` mappings.
5. The custom `discord_user_id` and expected officer identity data did not
   reach downstream services.
6. The visible failure emerged much later as authorization denials and e2e
   timeout behavior, specifically the officer queue bootstrap gate never
   reaching the expected row in e2e test 19.

The incident chain was:

- `init-127-applicant-discord-oauth` used an invalid model name and failed.
- `init-133B-pomerium-officer-discord` had the same model issue and also
  depended on `DISCORD_OFFICER_*` credentials.
- Authentik rolled back each failed blueprint transaction, so the intended
  custom source and scope mapping objects were not committed.
- The host-side Pomerium bootstrap still reconciled an Authentik provider
  named `pomerium`, but that helper binds only the three default scope mappings.
- Pomerium could authenticate, while the JWT lacked the custom claim data that
  the web/API layer depends on.

The important state is that the failing condition was present at Authentik's
blueprint instance layer, not at the Kubernetes apply layer.

## Architecture Review

### Where the blueprints come from

`bootstrap-blueprint-configmap.yaml` defines a single ConfigMap named
`authentik-init-114-blueprint` in `auth-system`. Its `data` keys contain three
mounted blueprint files:

- `init-114-local-users.yaml`
- `init-127-applicant-discord-oauth.yaml`
- `init-133B-pomerium-officer-discord.yaml`

The applicant blueprint declares:

- `authentik_sources_oauth.oauthsourcepropertymapping`
- `authentik_providers_oauth2.scopemapping` named
  `server-manager-applicant-discord_user_id`
- `authentik_sources_oauth.oauthsource` using
  `DISCORD_APPLICANT_OAUTH_CLIENT_ID` and
  `DISCORD_APPLICANT_OAUTH_CLIENT_SECRET`
- `authentik_providers_oauth2.oauth2provider` named
  `server-manager-applicant`
- `authentik_core.application` named `Server Manager Applicant`

The Pomerium officer blueprint declares:

- `authentik_sources_oauth.oauthsourcepropertymapping`
- `authentik_providers_oauth2.scopemapping` named
  `server-manager-pomerium-discord_user_id`
- `authentik_sources_oauth.oauthsource` using
  `DISCORD_OFFICER_OAUTH_CLIENT_ID` and
  `DISCORD_OFFICER_OAUTH_CLIENT_SECRET`
- `authentik_providers_oauth2.oauth2provider` named `pomerium`
- `authentik_core.application` named `Pomerium`

The Helm values mount only this one ConfigMap under
`blueprints.configMaps`. The rendered Authentik worker mounts it at
`/blueprints/mounted/cm-authentik-init-114-blueprint` and loads environment
from `Secret/authentik-config`.

`authentik-config` is produced by the Authentik InfisicalSecret template. The
template now includes `DISCORD_APPLICANT_*`, `DISCORD_OFFICER_*`,
`OIDC_CLIENT_*`, and `APPLICANT_OIDC_*` keys, but bootstrap currently verifies
only selected infrastructure readiness and sample secret behavior, not that
each Authentik blueprint consumed those values successfully.

### Who applies them

Authentik applies mounted blueprint instances from the worker process. The
official docs describe blueprint instances as YAML files mounted into the
worker container, read and applied regularly, and also applied after file
modification or discovery events. The same docs state that blueprint execution
is atomic: if any entry fails validation or errors, the blueprint transaction
is rolled back.

That means a malformed model name, empty required OAuth credentials, an
incompatible schema field, or a missing mounted file can fail independently of
Kubernetes object readiness.

### Bootstrap and reseed path

`bring-up-local-channel.sh` has two relevant paths:

- Normal setup calls `install_flux_post_install`, which runs
  `install-flux-for-channel.sh --channel "$CHANNEL_ID"`, then copies step-ca
  trust, then runs `bootstrap_pomerium_oidc_application`.
- `--reseed-gitserver-only` validates the existing k3d cluster and kubeconfig,
  then runs `install-flux-for-channel.sh --channel "$CHANNEL_ID"
  --reseed-gitserver-only` and exits.

`install-flux-for-channel.sh` normal setup:

- renders the local GitOps snapshot
- applies Flux controllers
- seeds the in-cluster git daemon
- applies the Flux source CRs
- waits for the GitRepository
- requests Kustomization reconciliation
- bootstraps Infisical credentials
- waits for Infisical runtime checks
- waits for `Kustomization/${SOURCE_NAME}` Ready

`install-flux-for-channel.sh --reseed-gitserver-only`:

- renders the local GitOps snapshot
- ensures and seeds the in-cluster git daemon
- applies the Flux source CRs
- waits for the GitRepository artifact revision to match the synthetic commit
- bounces OPAL and waits for OPAL Server/Client log signals
- prints the manual Flux resume command

Neither path queries Authentik blueprint instance state.

### The second Pomerium provider writer

`bring-up-local-channel.sh` also contains `bootstrap_pomerium_oidc_application`.
This helper port-forwards to Authentik, reads `AUTHENTIK_BOOTSTRAP_TOKEN`,
`OIDC_CLIENT_ID`, and `OIDC_CLIENT_SECRET`, fetches default flows and default
scope mappings, and then creates or patches the Authentik OAuth2 provider
named `pomerium`.

The payload constructed by this helper binds only:

- default `openid`
- default `email`
- default `profile`

It does not bind `server-manager-pomerium-discord_user_id`. Therefore it can
leave the system looking partially healthy even when the Pomerium officer
blueprint failed. Login can complete through a valid provider, but custom claim
mapping is absent.

This was the core masking behavior in the incident.

## Existing Health Checks

No existing bootstrap health check queries blueprint status.

Observed checks in `install-flux-for-channel.sh`:

- Flux CRDs and controller rollouts.
- Git daemon rollout and exec readiness.
- GitRepository Ready.
- GitRepository artifact revision in reseed mode.
- Kustomization Ready in full bootstrap.
- Infisical server, operator, selected secret keys, sample InfisicalSecret
  condition, and sample target Secret value.
- OPAL replacement and log signals in reseed mode.

Observed checks in `bring-up-local-channel.sh`:

- k3d cluster existence, kubeconfig match, node count, and node readiness.
- local toolchain presence.
- step-ca trust ConfigMap availability before copying trust to Pomerium.
- Authentik server rollout and HTTP readiness before the host-side Pomerium API
  bootstrap.
- presence of selected Authentik bootstrap inputs before the host-side
  Pomerium API bootstrap.

None of these checks inspect:

- `authentik_blueprints_blueprintinstance.status`
- `authentik_blueprints_blueprintinstance.last_applied_hash`
- the set of discovered mounted `init-*` blueprints
- whether the Pomerium and applicant providers have the expected custom
  property mappings after blueprint apply

## Authentik Status Query Surfaces

There are three practical query surfaces.

### Direct database query

The known table is `authentik_blueprints_blueprintinstance`, with relevant
columns:

- `name`
- `status`
- `last_applied_hash`
- `path`

This is the most direct runtime signal for this incident class. It can also
join or query provider and property mapping tables if a validator needs to
prove that custom mappings are attached to the expected providers. The
tradeoff is coupling to Authentik's internal PostgreSQL schema.

### Authentik REST API

The Authentik API reference exposes managed blueprint instance endpoints under
`/api/v3/managed/blueprints/`, including list/retrieve and apply operations.
The retrieve endpoint returns a blueprint instance object that includes fields
such as status in the documented API surface.

This avoids direct DB schema coupling and can be driven by the existing
bootstrap token through the same port-forward pattern already used by
`bootstrap_pomerium_oidc_application`. The tradeoff is that it needs an
available Authentik server, an API token, and careful pagination/filtering.

### `ak shell` inside the worker

`ak shell` can run ORM-backed inspection from the Authentik container context.
This avoids opening a DB connection from the host and can query Authentik
models directly. The tradeoff is operational awkwardness: it requires exec
access to the worker pod, depends on Authentik's management command/runtime
environment, and is less portable as a standalone validator.

For RCA purposes, all three can observe the failure. The direct DB path is the
simplest factual query. The REST API is the cleanest product API boundary.
`ak shell` is useful for ad hoc operator diagnosis.

## Existing Static Checks

`infra/tests/test_applicant_discord_blueprint.py` is static YAML validation.
It:

- loads `bootstrap-blueprint-configmap.yaml`
- uses a custom PyYAML loader to preserve Authentik tags like `!Env` and
  `!Find`
- flattens blueprint `entries`
- asserts expected model strings, source/provider/application declarations,
  env var names, custom `discord_user_id` mapping text, and scope text

It does not:

- start Authentik
- mount the ConfigMap into an Authentik worker
- call Authentik's blueprint importer
- query `authentik_blueprints_blueprintinstance`
- verify `last_applied_hash`
- verify the live provider-to-scope-mapping relation after apply
- catch Authentik schema changes where YAML remains structurally plausible but
  runtime validation rejects the payload

These tests can catch obvious checked-in YAML drift. They cannot catch the
class of runtime blueprint apply failure that produced BUG-8.

## Why Failures Go Silent Today

The failure is silent because each observer is watching a different layer:

- Flux watches Kubernetes apply and selected health checks. Authentik
  blueprint execution happens inside Authentik after the ConfigMap and worker
  Deployment exist.
- Authentik pod readiness uses `ak healthcheck`, which proves process and core
  dependency health, not mounted blueprint success.
- Infisical bootstrap checks verify operator and sample secret behavior, not
  every Authentik OAuth secret consumed by a blueprint.
- The static blueprint tests verify file shape, not Authentik's runtime import
  semantics.
- The host-side Pomerium provider bootstrap masks a missing blueprint by
  creating or patching a viable provider with only default mappings.
- Pomerium can complete OIDC login without the custom `discord_user_id` claim.
- Downstream services observe only missing identity/authorization context, so
  the symptom appears as queue gate failure, authorization denial, or a browser
  e2e timeout rather than as "blueprint failed."

The root cause is missing runtime health coverage for Authentik blueprint
instances and their downstream provider bindings.

## What Success Looks Like

After full bootstrap or after reseed plus Flux resume, the Authentik runtime
state should show every mounted `init-*` blueprint as applied:

- `status='successful'`
- `last_applied_hash` is non-empty
- `path` corresponds to the mounted blueprint path for the ConfigMap data
- no `init-*` mounted blueprint remains in `error`, unknown, or unapplied state

The identity-provider state should also match the contract:

- Applicant provider `server-manager-applicant` has the default OIDC mappings
  and the custom `server-manager-applicant-discord_user_id` mapping.
- Pomerium provider `pomerium` has the default OIDC mappings and the custom
  `server-manager-pomerium-discord_user_id` mapping.
- The mounted worker path exists for the ConfigMap files.
- The `authentik-config` Secret contains non-empty values for all blueprint
  env inputs that have no safe empty runtime behavior, including
  `DISCORD_APPLICANT_OAUTH_CLIENT_ID`,
  `DISCORD_APPLICANT_OAUTH_CLIENT_SECRET`,
  `DISCORD_OFFICER_OAUTH_CLIENT_ID`, and
  `DISCORD_OFFICER_OAUTH_CLIENT_SECRET`.

This "success" definition is broader than Kubernetes readiness. It is the
minimum runtime state needed to prevent "login works but claims are missing."

## Failure Modes Worth Catching

- Wrong Authentik model name: YAML can parse and static tests can even assert
  the intended string, while Authentik rejects the model at apply time.
- Missing env var: `!Env [NAME, ""]` can produce an empty OAuth credential that
  fails validation or produces a broken source.
- Schema-incompatible payload: an Authentik version upgrade can drop, rename,
  or tighten a field while Kubernetes and YAML parsing still pass.
- Blueprint ConfigMap not mounted on the worker: Flux can apply the ConfigMap,
  but the worker may not discover the file if Helm values, rendered mounts, or
  Deployment rollout state drift.
- Masked provider fallback: a separate bootstrap helper can create a provider
  with default mappings only, hiding blueprint failure until downstream claim
  checks.

## Solution Candidates

These are candidate intervention points, not a recommended fix.

### Option A: Add blueprint health check to `reseed_gitserver_only`

Mechanism: after the GitRepository reaches the expected artifact and after the
relevant Flux apply point, query Authentik runtime state for all `init-*`
blueprints and fail if any are not `successful` with a non-empty
`last_applied_hash`. The same check could also inspect provider mappings.

Tradeoffs:

- Catches the exact incident path close to the operator action that refreshed
  GitOps state.
- Pairs naturally with BUG-4/BUG-6 reseed workflow, where stale GitOps source
  and OPAL policy refresh are already being verified.
- Needs a clear wait boundary because `--reseed-gitserver-only` currently
  waits for GitRepository artifact revision and OPAL logs, then tells the user
  how to resume Flux. If Flux remains suspended, Authentik may not have applied
  the updated ConfigMap yet.
- Couples reseed to Authentik availability. That is useful when the reseed
  changes Authentik blueprints, but heavier when reseeding unrelated manifests.

### Option B: Add standalone blueprint validator

Mechanism: create a runtime validator in `infra/tests/validate_*_blueprints.sh`
or equivalent that waits for Authentik and checks blueprint instance state,
hashes, mounts, and provider mappings.

Tradeoffs:

- Keeps validation reusable from local e2e, manual diagnosis, and bootstrap.
- Can be run after Flux resume, avoiding ambiguity in the suspended reseed
  phase.
- Gives a named, focused failure message instead of an e2e timeout.
- Only protects flows that call it. If bootstrap and e2e do not invoke it, the
  silent failure class remains.

### Option C: Add a Kubernetes Job for blueprint health

Mechanism: deploy a Job or similar in-cluster health resource that queries
Authentik blueprint state and fails visibly when any required blueprint is in
error or unapplied.

Tradeoffs:

- Moves the health signal into the cluster and can be attached to namespace or
  Flux health behavior.
- Can catch failures continuously after GitOps apply, not only from host-side
  scripts.
- Needs credentials and network policy allowance to query Authentik or its
  database.
- Needs careful ordering so it runs after Authentik worker discovery and apply,
  not before the worker has had a chance to process mounted files.
- More moving parts than a host-side script or test validator.

### Option D: Authentik webhook or event integration

Mechanism: consume Authentik events or webhook-like notifications for blueprint
apply errors and route them to logs, alerts, or a bootstrap gate.

Tradeoffs:

- Best long-term observability posture if Authentik emits stable events for
  blueprint failures.
- Can surface future failures outside local bootstrap and e2e.
- Does not by itself prove post-reseed desired state unless paired with a
  state query.
- Requires additional event plumbing and alert lifecycle work, which is larger
  than the immediate local failure gate.

## Affected Paths

- `gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml`
  - source of the mounted `init-*` blueprint files and custom mappings
- `gitops/channels/local/auth/authentik/render-values.yaml`
  - declares mounted Authentik blueprint ConfigMaps
- `gitops/channels/local/auth/authentik/rendered/authentik-2026.2.2.yaml`
  - rendered worker mount and readiness behavior
- `gitops/channels/local/auth/authentik/secrets-infisicalsecret.yaml`
  - produces `authentik-config` and the Discord/OIDC env inputs used by
    blueprints
- `gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml`
  - Pomerium requests `openid email profile discord_user_id` and forwards
    claim headers
- `infra/scripts/install-flux-for-channel.sh`
  - full bootstrap and reseed sequencing; no blueprint status query today
- `infra/scripts/bring-up-local-channel.sh`
  - calls the Flux installer and runs the host-side Pomerium Authentik API
    bootstrap with default mappings only
- `infra/tests/test_applicant_discord_blueprint.py`
  - static YAML tests; no runtime Authentik apply coverage
- `infra/tests/validate_web_ui_local.sh`
  - downstream validation currently depends on identity claims being present
    rather than proving their Authentik source first
- `infra/tests/e2e/tests/19-web-ui.sh`
  - downstream timeout surface observed during the incident

## Not Proposing Fix

This RCA does not choose among the candidate interventions and does not
implement any change. The root cause is the absence of runtime blueprint
health validation at the bootstrap/reseed/e2e boundary, compounded by a
host-side Pomerium provider bootstrap that can leave authentication functional
with only default scope mappings after a blueprint failure.
