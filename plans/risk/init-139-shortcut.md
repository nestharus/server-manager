# INIT-139 — Shortcut risk gate (Kong KIC translation smoke)

**Verdict:** LOW

Scope: INIT-139 — runtime smoke that proves KIC translates the
`konghq.com/plugins: public-intake-rate-limit` Ingress
annotation into Kong Route-scoped `rate-limiting` plugin
entities, not just that the manifest YAML is correct. The slice
adds one new shell validator
(`infra/tests/validate_kong_kic_translation_local.sh`), wires it
into the cluster-runtime lane in `.buildkite/pipeline-cluster.yml`,
and adds two pytest guards (validator-contents guard and
Buildkite-wiring guard).

The shortcut gate inspects whether INIT-139 ships a real
port-forward to Kong's Admin API (not "trust the manifest"), real
`/routes` and `/routes/<id>/plugins` queries (not a pure-static
check renamed `--cluster`), both positive and negative
assertions, no "TODO: add adjacency check later" stubs, a pytest
guard that reads the validator script (catches silent removal),
and a Buildkite step that is genuinely wired with a pytest
assertion to enforce the wiring.

Source: `proposals/34-init-139-kong-kic-smoke.md`,
`research/50-init-139-kic-smoke-problem-map.md`,
`.buildkite/pipeline-cluster.yml`.

## C1 — Real port-forward to Kong Admin API (not "trust manifest YAML")

**Pass.**

Q3 (proposal lines 75-96) locks a real port-forward access path,
not a static manifest read:

> ```bash
> kubectl port-forward deploy/kong-kong -n kong 8444:8444 &
> curl --fail --silent --show-error --insecure https://localhost:8444/routes
> ```

The Substrate (line 184) restates this as a runtime contract:
"Port-forwards Admin API HTTPS `8444`." Anti-scope (line 264)
explicitly forbids the cheap-trick alternative ("Behavior burst
test. That is a separate slice if needed.") and the pure-static
alternative is structurally absent — TG-1 (lines 211-223) requires
"the script reaches Kong Admin API through the `8444`
port-forward." The validator is also explicitly not allowed to
become a second BL-014 static check (Q2 line 72: "This validator
is runtime-only. It does not add another static manifest check
for BL-014.").

The proposal additionally requires a `trap` cleanup of the
port-forward process (line 90), which is the right shape for a
short-lived live introspection, not a manifest-only assertion.

**Risk:** the shortcut would be (a) fall back to `kubectl get
kongplugin -o yaml | grep route` and call it a "translation
smoke" because port-forward is flaky on the runner, (b) read
`gitops/channels/local/.../kong-3.2.0.yaml` and assert that the
plugin CRD exists, calling that "the runtime check," or (c) skip
the port-forward and `curl` against a Kubernetes `Service` that
does not exist (the rendered chart binds the Admin API to
pod-local loopback — research lines 50-51).

**Mitigation:** Q3 locks `kubectl port-forward` against
`deploy/kong-kong` on `8444:8444`, with `--insecure` against
`localhost`, plus a trap. Anti-scope rules out the burst-only
escape. TG-2 (see C5) makes the validator script itself the
substrate of test enforcement, so a regression to a static-only
implementation would have to also rewrite the pytest guard's
assertions.

**Adjacent execution risk (not a shortcut):** Q3 also flags an
unresolved namespace mismatch — the rendered Kong release is
under `kong-system` (confirmed in
`gitops/channels/local/ingress/kong/namespace.yaml`), but the
locked port-forward command targets namespace `kong`. The
proposal forces this to be reconciled during implementation and
explicitly forbids using it as a reason to switch to burst
behavior. This is an execution detail to land cleanly during
implementation, not a shortcut path the gate must reject; flagging
it for the implementer.

## C2 — Real `/routes` + `/plugins` queries

**Pass.**

Q4 (proposal lines 99-118) locks paginated `GET /routes` and
forbids generated route names:

> Lock: discover routes through paginated `GET /routes`. ...
> The validator must not use generated route names. It must
> identify routes by route attributes: `hosts` contains the
> expected host; `paths` contains the expected path ...

Q5 (lines 121-130) locks the per-route plugin query:

> Lock: for each selected route, call `GET /routes/<route_id>/plugins`.
> For every public-intake route, assert that the returned plugin
> list contains an enabled plugin with `name == "rate-limiting"`.

The Substrate (lines 185-187) restates both queries as required
script behavior. TG-1 acceptance (lines 218-220) requires
"all five public-intake host/path routes are found through
`GET /routes`" and "every public-intake route has a route-scoped
enabled `rate-limiting` plugin." TG-2 acceptance (lines 237-239)
asserts the script contains both endpoint strings and the
`rate-limiting` literal.

The route identity rule (host + path attribute match, paginated)
is the right one — KIC route names are templated and fragile, so
asserting on `hosts`/`paths` from the Admin API JSON is the
substantive translation check.

**Risk:** the shortcut would be (a) pull only `/routes` and
infer plugin presence from `route.tags` or a guessed plugin name
in `/plugins`, never actually calling
`/routes/<id>/plugins`, (b) match by Kong-generated route name
(`server-manager-public-intake-api.api-local-humility-local.0`
or similar) and silently pass when KIC renames routes, or (c)
read `/plugins` once and search the response for `"name":
"rate-limiting"` without checking the per-route binding (the
exact failure mode BL-014 is supposed to catch).

**Mitigation:** Q4 forbids name-based identity, Q5 forbids
plugin-list-only assertions by mandating the route-scoped
endpoint, and TG-2 asserts both literal strings appear in the
script. The plugin assertion is also against the Kong plugin
type (`rate-limiting`), not the K8s `KongPlugin` CR name (Q5
line 127), which is the correct level — the CR name is what KIC
reads, the plugin type is what Kong actually enforces.

## C3 — Both positive AND negative assertions present

**Pass.**

Positive set (Q4 lines 110-115): five host/path pairs across
both API and web hostnames.

Negative set (Q6 lines 132-150): required negative is
`api.local.humility.local` + `/api/v1/web/admin/chapters`.
Optional additional negatives are listed for the catch-all
routes if present (`web.local.humility.local /`,
`protected-api.local.humility.local /`), but Q6 explicitly
refuses to let optional-negative absence cover for required-
negative absence:

> Do not treat a missing optional adjacent route as a pass for
> the required admin-path negative. The required negative must
> resolve to exactly one route or fail with route-listing
> diagnostics.

TG-1 acceptance (lines 220-223) requires the admin-path negative
to resolve to its route and have no route-scoped `rate-limiting`
plugin. TG-2 acceptance (line 242) asserts the script contains
the `/api/v1/web/admin/chapters` literal.

The negative assertion is the substantive one — the BL-014
silent-drop scenario is exactly "all the right plugins exist
somewhere, but nothing is bound to the public-intake routes,"
and asserting only positives would not catch a worse drift where
the plugin is bound globally or to the catch-alls.

**Risk:** the shortcut would be (a) ship only the five positive
checks and rely on the diff comment "negative coverage in
follow-up," (b) treat "no rate-limiting plugin found anywhere
on this host" as the negative, missing the case where the
plugin is route-scoped on the wrong route, or (c) make the
negative a soft warning (`echo "WARN:"`) instead of a failing
assertion.

**Mitigation:** Q6 enumerates the required negative explicitly,
forbids it being downgraded to optional-only coverage, and
defines the resolution rule (host + route path → exactly one
route or fail with diagnostics). TG-1 ranks the negative
acceptance alongside the positive set, and TG-2 asserts the
literal in the script.

## C4 — No "TODO: add adjacency check later" stubs

**Pass.**

Q6 lands the adjacency check in this slice, not in a follow-up.
There is no "TODO," "later," "phase 2," or "follow-up" deferral
language anywhere in the proposal's Q6 or Substrate. The
Anti-scope (lines 263-273) lists what is explicitly out — burst
testing, kind/k3d ephemeral fixtures, Kong/KIC manifest
changes, BL-014 pin changes, compatibility shims, and Discord
mutations — and the adjacency check is conspicuously not on that
deferral list.

TG-2 (line 242) hard-asserts the script contains the
`/api/v1/web/admin/chapters` literal, so a "remove the negative
to land faster" attempt during implementation would fail the
guard rather than slip through.

**Risk:** the shortcut would be (a) leave a `# TODO: add adjacency
check after first green CI run` comment in the validator and
file a follow-up ticket, (b) implement the adjacency check as
a logged warning that doesn't fail the script, or (c) gate the
adjacency check behind a flag that defaults to off.

**Mitigation:** the proposal does not allow any of these — Q6
locks the assertion as required, TG-1 makes it part of validator
acceptance, and TG-2 statically enforces its presence in the
script's text. There is no flag, env var, or `--skip-negative`
escape hatch defined.

## C5 — Pytest guard reads validator script (catches silent removal)

**Pass.**

TG-2 (proposal lines 226-243) explicitly reads the validator
script and asserts on its contents:

> - pytest reads `infra/tests/validate_kong_kic_translation_local.sh`;
> - the guard asserts the script contains the expected
>   public-intake route set;
> - the guard asserts the script checks `GET /routes`;
> - the guard asserts the script checks `GET /routes/<route_id>/plugins`;
> - the guard asserts the script searches for `rate-limiting`;
> - the guard asserts the script contains the adjacent
>   `/api/v1/web/admin/chapters` negative.

TG-2's stated purpose (line 244-245) names the regression class
the guard prevents:

> This catches accidental deletion, broadening, or replacement
> with a weaker static-only validator.

This is the right shape: the guard does not try to execute the
shell script (which would require a live cluster from pytest),
it reads the file and pattern-matches. That is the substantive
"silent removal" defense — if a future PR deletes the validator,
weakens it, or replaces it with a stub, pytest fails before
runtime CI ever gets a chance.

**Risk:** the shortcut would be (a) skip TG-2 entirely on the
basis that "TG-1 already runs the validator," missing the silent-
removal case where the validator simply isn't called from CI,
(b) implement the guard as `assert os.path.exists(...)` only,
which catches deletion but not weakening, or (c) implement the
guard as `assert "rate-limiting" in script_text` only, which
catches deletion but not broadening or `--cluster`-flag removal.

**Mitigation:** TG-2 enumerates six distinct content assertions
covering route set, both endpoints, the plugin name, and the
adjacency negative. That is enough surface area to catch the
weakening cases the static-only-replacement risk implies.

**Adjacent gap (worth flagging, not blocking):** the guard does
not appear to assert that the script contains the
`port-forward` or `8444` literal. A regression that turned the
validator into a `kubectl get kongplugin` static dump while
keeping the route-set strings would technically pass TG-2.
Consider adding `port-forward` and `8444` to the TG-2 literal
set during implementation. This is a refinement, not a
shortcut-gate fail, because TG-1 still requires the live Admin
API connection.

## C6 — Buildkite step actually wired (test asserts pipeline yaml has it)

**Pass.**

Substrate (proposal lines 191-198) locks the pipeline edit:

> - `.buildkite/pipeline-cluster.yml`
>   - Add the new validator to the
>     `pr-cluster-merge-readiness-runtime-validators` command block.
>   - Place it after Kong, TLS/DNS, auth/server-manager, or
>     existing readiness validators have made the live route
>     state meaningful.
>   - Keep it in the cluster-runtime lane, not `.buildkite/pipeline.yml`.

TG-3 (lines 246-260) wires the structural assertion:

> - pytest loads `.buildkite/pipeline-cluster.yml` with
>   `yaml.safe_load`;
> - the cluster runtime validator step command includes
>   `infra/tests/validate_kong_kic_translation_local.sh --cluster`;
> - the assertion fails if the validator is only present in
>   comments, only in `.buildkite/pipeline.yml`, or missing
>   from the PR cluster runtime lane.

The "comments only" exclusion is the substantive one — that is
the most plausible silent-disable shortcut, and TG-3 explicitly
calls it out.

The current `.buildkite/pipeline-cluster.yml`
(`pr-cluster-merge-readiness-runtime-validators` block, lines
25-35) shows where the validator must be added. The proposal
correctly notes the cluster lane, not the default `pipeline.yml`,
is the right home — the validator needs a live Kong data plane.
An existing pytest test
(`infra/tests/buildkite_pipeline/test_cluster_lane.py`) already
owns cluster-lane assertions, which is the natural extension
point per the proposal's diff-budget note (lines 285-286:
"preferably extending an existing Buildkite pipeline test if
one already owns cluster-lane assertions").

**Risk:** the shortcut would be (a) add the validator only to
`pipeline.yml` because "the unit-test lane is faster" (validator
fails because no Kong data plane), (b) add the validator
inside a Buildkite step `if:` gate that always evaluates false
on PRs, (c) leave the validator referenced only in a comment in
`pipeline-cluster.yml`, or (d) add the validator step but skip
the `--cluster` flag so it short-circuits to a no-op static
check.

**Mitigation:** TG-3 uses `yaml.safe_load` (so comments are
ignored — comment-only references fail), explicitly asserts
against `pipeline-cluster.yml` (so misplacement to `pipeline.yml`
fails), and asserts the literal includes `--cluster` (so
flag-stripping fails). The three most plausible silent-disable
shortcuts are each named and structurally rejected.

**Adjacent gap (worth flagging, not blocking):** the cluster
lane currently runs with `--cluster-only`, which the problem map
(research lines 21, 35) flags as skipping Flux post-install —
the smoke is meaningless against an empty k3d cluster. The
problem map asks the proposal to "either rely on a pre-existing
cluster state that the lane already preserves in practice, or
explicitly lock the bootstrap/reseed prerequisite before adding
the validator." The proposal does not visibly resolve this. If
the cluster lane is truly empty post-bringup, TG-1 would fail
deterministically with "no routes found," which is a loud
failure rather than a silent shortcut, but it is still a real
implementation prerequisite. Flag for the implementer to confirm
cluster reconciliation state before TG-1 can pass; do not block
the gate, because deterministic loud failure is not a shortcut
path.

## Verdict

**LOW.** All six shortcut checks pass. The proposal:

- Locks a real `kubectl port-forward` to the Kong Admin API
  on HTTPS `8444` with `--insecure` and `trap` cleanup, not a
  manifest-only assertion (C1).
- Mandates paginated `GET /routes` plus per-route
  `GET /routes/<id>/plugins`, with route identity by `hosts` +
  `paths` rather than KIC-generated route names, and plugin
  identity by Kong plugin type `rate-limiting` (C2).
- Requires both the five public-intake positive bindings and a
  required adjacent admin-path negative
  (`/api/v1/web/admin/chapters`), with optional-negative absence
  not allowed to substitute for required-negative absence (C3).
- Lands the adjacency check in this slice with no deferral or
  follow-up language; TG-2 hard-asserts the literal in the
  script (C4).
- Adds a pytest guard that reads the shell validator and
  asserts on six distinct content patterns, naming "accidental
  deletion, broadening, or replacement with a weaker static-only
  validator" as the regression class (C5).
- Adds a pytest guard against `pipeline-cluster.yml` parsed
  with `yaml.safe_load`, explicitly rejecting comment-only,
  wrong-lane, and missing-`--cluster` shortcuts (C6).

Two adjacent execution risks worth flagging to the implementer
(neither blocks the shortcut gate, because both fail loudly
rather than silently):

1. **Kong namespace mismatch.** Q3 locks `-n kong` but the
   rendered chart is under `kong-system`. Reconcile during
   implementation; do not switch to burst behavior to avoid it
   (Q3 already forbids that path).
2. **Cluster lane bootstrap.** The cluster lane runs with
   `--cluster-only`, which skips Flux post-install. If the
   k3d cluster has no reconciled GitOps state, TG-1 will fail
   deterministically with "no routes found." Confirm the lane's
   actual reconciled state, or lock a bootstrap/reseed
   prerequisite before TG-1 can pass.

One refinement worth considering during implementation, not
blocking: TG-2's literal set could include `port-forward` and
`8444` to harden against a regression that strips the live
Admin API access while keeping the route-set strings.

SHORTCUT_DONE: plans/risk/init-139-shortcut.md
