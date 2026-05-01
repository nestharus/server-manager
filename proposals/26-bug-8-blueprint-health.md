# Proposal 26 - BUG-8: Authentik blueprint health check

## 1. Problem statement

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

## 2. Decisions

### Q1. Intervention point

Lock: candidate B, a standalone Authentik blueprint validator, plus invocation
from the BUG-4/BUG-6 reseed path.

The validator is the durable unit because BUG-8 is not only a reseed problem:
the same failure can appear after fresh bootstrap, local e2e setup, or manual
diagnosis. Reseed still gets a first-class call site so the BUG-4/BUG-6
operator path fails before downstream OAuth, Pomerium, Cedar, or SPA checks
hide the real cause.

Do not pick candidate A alone. A reseed-only health check would miss the e2e
and manual validation surfaces. Do not pick C or D for this bug. A Kubernetes
Job, webhook, or event pipeline can become longer-term observability, but BUG-8
needs a narrow host-side gate that can be called by existing local scripts.

### Q2. Validator location

Lock: add `infra/tests/validate_authentik_blueprints_local.sh`.

This follows the local validator naming pattern already used by
`validate_web_ui_local.sh`, `validate_auth_stack_local.sh`, and sibling
`validate_*_local.sh` scripts. The script should accept at least:

- `--kubeconfig PATH`, defaulting to `~/.kube/humility-local.yaml`;
- `--channel local`, if channel resolution is needed for future consistency;
- `-h|--help`.

Do not bury the check inside `validate_web_ui_local.sh`. The web UI validator
should call it, but the blueprint health contract belongs to Authentik runtime
state and must remain callable independently.

### Q3. State query surface

Lock: query Authentik PostgreSQL directly with `kubectl exec` into the local
CNPG primary pod and `psql`.

The validator should select the primary pod for
`Cluster/auth-system/authentik-postgres` by label instead of hard-coding
`authentik-postgres-1`, then execute `psql` inside the `postgres` container
against the `authentik` database using the in-cluster application connection
details. This preserves the operational shape of the suggested command:

```text
kubectl --kubeconfig "$KUBECONFIG_PATH" -n auth-system exec -i <authentik-postgres-primary> -c postgres -- psql ...
```

Use the database rather than the Authentik REST API for BUG-8. The failing
condition was stored in `authentik_blueprints_blueprintinstance`, and the
provider-to-scope relation is also database state. A REST validator would
depend on Authentik server API availability, token plumbing, pagination, and
the same host-side API route that is not needed to observe this failure.

Failure output must include:

- blueprint `name`;
- blueprint `path`;
- `status`;
- `last_applied_hash`;
- the stored diagnostic context/content available on the blueprint instance
  row, and recent Authentik worker log lines for that blueprint when the row is
  in a failing state.

That combination satisfies the debugging contract: the operator sees the
specific blueprint and the apply error context before Playwright or downstream
authorization has a chance to time out.

### Q4. Assertion list

Lock the validator to these runtime assertions:

1. Every mounted `init-*` blueprint instance is present in
   `authentik_blueprints_blueprintinstance`.
2. Every `init-*` blueprint has `status = 'successful'`.
3. Every `init-*` blueprint has a non-empty `last_applied_hash`.
4. The custom scope mapping
   `server-manager-pomerium-discord_user_id` exists.
5. The custom scope mapping
   `server-manager-applicant-discord_user_id` exists.
6. The OAuth2 provider `pomerium` has at least these four property mappings:
   default `openid`, default `email`, default `profile`, and
   `server-manager-pomerium-discord_user_id`.
7. The OAuth2 provider `server-manager-applicant` has at least these four
   property mappings: default `openid`, default `email`, default `profile`,
   and `server-manager-applicant-discord_user_id`.
8. The Authentik application `pomerium` links to the OAuth2 provider
   `pomerium`.

The script may print extra diagnostics, but these are the blocking checks.
Missing custom mappings must fail even if the provider exists and login would
otherwise work with the three default OIDC mappings.

### Q5. Invocation points

Lock three call sites:

1. `infra/scripts/install-flux-for-channel.sh`
   - In `reseed_gitserver_only`, call
     `infra/tests/validate_authentik_blueprints_local.sh --kubeconfig "$KUBECONFIG_PATH"`
     after `bounce_opal_for_reseed`.
   - This means the BUG-6 reseed recovery first confirms the new GitRepository
     revision and OPAL bundle refresh, then fails the reseed if Authentik
     blueprint runtime state is broken.
   - The call should be blocking. A failed blueprint validator exits the
     reseed script non-zero.

2. `infra/tests/e2e/tests/19-web-ui.sh`
   - Run the validator before the Playwright browser flow.
   - The current script already calls `run_validator validate-web-ui
     infra/tests/validate_web_ui_local.sh ...`; the new preflight should run
     before the browser OAuth flow so blueprint failures surface as named
     Authentik errors instead of officer queue timeouts.

3. `infra/tests/validate_web_ui_local.sh`
   - Call the Authentik blueprint validator as part of runtime proof when not
     in `--static-only` mode.
   - The web UI runtime proof depends on Pomerium/Authentik custom identity
     claims; it should first prove the source of those claims is healthy.

## 3. Substrate

### New file

- `infra/tests/validate_authentik_blueprints_local.sh`
  - Add the standalone runtime validator.
  - Follow the pass/fail/skip/result style used by existing local validators.
  - Require `kubectl` and `psql` through the in-cluster Postgres pod; do not
    require a local Postgres client.
  - Resolve the Authentik Postgres primary pod dynamically.
  - Query blueprint instance state and provider binding state through SQL.
  - Emit failure messages that name the failed blueprint or provider and list
    missing mappings.

### Modified files

- `infra/scripts/install-flux-for-channel.sh`
  - Add a validator constant near the other script paths.
  - Add one blocking call in `reseed_gitserver_only` after
    `bounce_opal_for_reseed`.
  - Keep the manual Flux resume guidance, but do not print it after a failed
    Authentik blueprint check.

- `infra/tests/e2e/tests/19-web-ui.sh`
  - Add the Authentik blueprint preflight before Playwright.
  - Keep the existing `validate_web_ui_local.sh` call and downstream database
    assertions.

- `infra/tests/validate_web_ui_local.sh`
  - Invoke the new validator from runtime validation.
  - Skip the Authentik runtime call under `--static-only`.

### Unmodified substrate

- Do not modify Authentik blueprint YAML content as part of this proposal.
- Do not change `bring-up-local-channel.sh`'s host-side Pomerium provider
  bootstrap in this proposal. BUG-8 detects the masking behavior; removing or
  changing that helper is a separate design question.
- Do not modify API, web, Discord daemon, migrations, or Pomerium manifests.

## 4. Test plan

### TG-1: current healthy cluster passes

Run the validator against the current healthy local cluster:

```bash
bash infra/tests/validate_authentik_blueprints_local.sh \
  --kubeconfig ~/.kube/humility-local.yaml
```

Acceptance:

- every mounted `init-*` blueprint reports `status = 'successful'`;
- every mounted `init-*` blueprint reports non-empty `last_applied_hash`;
- both custom `discord_user_id` scope mappings exist;
- both OAuth2 providers have the default OIDC mappings plus their custom
  Discord mapping;
- the `pomerium` application links to the `pomerium` provider;
- the script exits zero and prints a `RESULT: pass=... fail=0 skip=...`
  summary.

### TG-2: corrupted blueprint fails with named error

Manually corrupt a mounted blueprint in a local test branch or temporary
cluster state, for example by injecting an invalid Authentik model name into
one `init-*` blueprint, then reconcile Authentik and run the validator.

Acceptance:

- the validator exits non-zero;
- the failure names the exact blueprint, for example
  `init-127-applicant-discord-oauth` or
  `init-133B-pomerium-officer-discord`;
- the failure includes `status`, `path`, `last_applied_hash`, and the
  available apply diagnostic context or worker log excerpt;
- Playwright is not needed to discover the failure.

### TG-3: reseed flow integration

Run the BUG-4/BUG-6 reseed flow after the validator call is wired:

```bash
bash infra/scripts/bring-up-local-channel.sh \
  --channel local \
  --reseed-gitserver-only
```

Acceptance:

- the reseed still renders and seeds the local GitOps snapshot;
- `GitRepository/flux-system/humility-local` reaches the seeded revision;
- BUG-6 OPAL bounce completes and OPAL Client fetches the refreshed bundle;
- the Authentik blueprint validator runs after the OPAL bounce;
- if a blueprint is in `error` or missing its hash, reseed exits non-zero and
  names the failed blueprint;
- if provider mappings are missing, reseed exits non-zero and names the
  provider plus missing mapping names.

## 5. Anti-scope

Do not add a Kubernetes Job or webhook. BUG-8 needs a host-side validator that
can be invoked from existing scripts and e2e preflight.

Do not change the Authentik image, Helm chart version, or runtime version.
This proposal observes the existing Authentik runtime state; it does not
upgrade or patch Authentik.

Do not modify the blueprint ConfigMap structure beyond adding the validator
and call sites. The validator checks the mounted `init-*` blueprint contract
as it exists today.

Do not add a fallback REST API path, compatibility shim, feature flag, or
warning-only mode. The selected health gate is direct database validation, and
failures should fail the calling script.

Do not broaden the web e2e flow or add new Playwright behavior. The point is
to fail before Playwright when Authentik runtime state is already invalid.

## 6. Diff budget

Expected implementation size: one new validator script and three small call
site edits.

Budget:

- `infra/tests/validate_authentik_blueprints_local.sh`: roughly 140-220 lines
  for argument parsing, pass/fail helpers, pod discovery, SQL execution, and
  focused assertions.
- `infra/scripts/install-flux-for-channel.sh`: under 20 lines for a script
  constant and one blocking reseed call after `bounce_opal_for_reseed`.
- `infra/tests/e2e/tests/19-web-ui.sh`: under 10 lines for the preflight call.
- `infra/tests/validate_web_ui_local.sh`: under 20 lines for runtime invocation
  and static-only skip behavior.
- No GitOps manifest churn.
- No production service code.
- No migrations.
