# BUG-8 Scope risk gate

Verdict: **PASS**

Reviewed:

- `proposals/26-bug-8-blueprint-health.md`
- `research/39-bug-8-blueprint-health-rca.md`

## Findings

### 1. Only adds `infra/tests/validate_authentik_blueprints_local.sh` + extends 3 callers — PASS

Proposal §3 declares exactly one new file and exactly three modified files,
matching the gate criterion 1:1:

- New file: `infra/tests/validate_authentik_blueprints_local.sh` — the
  standalone runtime validator. Q2 locks this filename and its placement
  next to the existing `validate_*_local.sh` family
  (`validate_web_ui_local.sh`, `validate_auth_stack_local.sh`).
- Modified caller 1: `infra/scripts/install-flux-for-channel.sh` — adds a
  validator-path constant near the other script paths and one blocking
  call inside `reseed_gitserver_only` after `bounce_opal_for_reseed`. Q5
  locks this as the BUG-4/BUG-6 reseed call site.
- Modified caller 2: `infra/tests/e2e/tests/19-web-ui.sh` — adds a
  preflight call before the existing Playwright browser flow. Q5 locks
  this as the e2e call site so blueprint failures surface before the
  officer queue timeout that originally hid the incident.
- Modified caller 3: `infra/tests/validate_web_ui_local.sh` — invokes the
  new validator from runtime validation and skips it under
  `--static-only`. Q5 locks this as the third call site so the web UI
  runtime proof first proves the source of its custom claims.

Diff budget §6 caps the change at "one new validator script and three
small call site edits" with explicit per-file line bounds (validator
~140-220 lines; the three callers all under 20 lines each), and §3
"Unmodified substrate" explicitly forbids touching
`bring-up-local-channel.sh`'s host-side Pomerium provider bootstrap as
part of this proposal even though the RCA names it as the masking
helper.

### 2. No production code, image, or YAML schema changes — PASS

Proposal §3 "Unmodified substrate" is explicit on all three sub-criteria:

- "Do not modify Authentik blueprint YAML content as part of this
  proposal." — no YAML schema changes.
- "Do not modify API, web, Discord daemon, migrations, or Pomerium
  manifests." — no production code changes.
- Anti-scope §5: "Do not change the Authentik image, Helm chart version,
  or runtime version. This proposal observes the existing Authentik
  runtime state; it does not upgrade or patch Authentik." — no image
  changes.
- Anti-scope §5: "Do not modify the blueprint ConfigMap structure beyond
  adding the validator and call sites. The validator checks the mounted
  `init-*` blueprint contract as it exists today." — no ConfigMap or
  rendered-Helm schema changes.

Diff budget §6 reinforces with three "No" lines: "No GitOps manifest
churn. No production service code. No migrations." Q3 locks the state
query as a read-only `SELECT` against
`authentik_blueprints_blueprintinstance` (and provider/property-mapping
joins) — no DDL, no inserts, no updates against Authentik's database.

### 3. No new dependencies — PASS

Proposal §3 "New file" specifies the validator must "Require `kubectl`
and `psql` through the in-cluster Postgres pod; do not require a local
Postgres client." Both tools are already required by sibling
`validate_*_local.sh` scripts (`kubectl` is universal across the local
validator family; `psql` is invoked inside the existing
`Cluster/auth-system/authentik-postgres` primary pod via `kubectl exec
-c postgres`, so no host-side Postgres client appears in the host
toolchain). Q3 explicitly chose the in-pod `psql` path "rather than the
Authentik REST API" precisely to avoid adding "Authentik server API
availability, token plumbing, pagination, and the same host-side API
route" as new prerequisites.

No new package, library, gem, container image, Helm chart, CRD, or
operator is introduced. The validator is a bash script consuming tools
already present in the local-bringup contract.

### 4. No webhook / Kubernetes Job — PASS

Anti-scope §5 (first paragraph): "Do not add a Kubernetes Job or
webhook. BUG-8 needs a host-side validator that can be invoked from
existing scripts and e2e preflight." This is the gate criterion stated
verbatim.

Q1 ("Intervention point") explicitly considered and rejected the RCA's
Candidate C (Kubernetes Job) and Candidate D (Authentik webhook /
event integration), locking instead on Candidate B (standalone
host-side validator) plus a reseed call site. The chosen mechanism is
a bash script invoked synchronously from existing operator scripts and
e2e preflight — no in-cluster resource is created, no controller is
deployed, no event listener is registered.

## Conclusion

The proposal confines the BUG-8 fix to one new host-side bash validator
plus three exactly-named caller edits, makes no production code, image,
Helm chart, or YAML schema changes, introduces no new dependencies
beyond `kubectl` and the in-pod `psql` already available through the
existing CNPG Postgres primary, and explicitly rejects the Kubernetes
Job and webhook candidates. Each of the four gate checks passes against
specific proposal sections. Scope risk is acceptable.

SCOPE_DONE: plans/risk/bug-8-scope.md
