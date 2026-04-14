# Phase 1 Foundation v2 — Audit risk assessment

Subject: `plans/proposals/phase1-foundation-v2.md`
Scope: credential exposure, network security, infrastructure
misconfiguration, secret handling, Vultr API key management, storage
class correctness, Flux bootstrap security, benchmark data integrity,
LLM video QA data handling.

## Verdict: MEDIUM

The proposal corrects several real audit defects in the current draft
(Hetzner storage class, single-path Flux, cross-environment secret
ambiguity, shared Discord bot identity). It is credible, internally
consistent, and aligned with `AGENTS.md` Live Server Principle. But it
leaves six material audit concerns implicit or unspecified that need to
be explicit before the risk gate can return LOW. None are blocking in
the "this proposal is dangerous" sense; all are "the proposal does not
yet tell a reviewer how a sensible operator would avoid the obvious
failure mode."

## Findings

### 1. Vultr API key and Object Storage credential management — MEDIUM

The proposal never states who owns the Vultr API key, how it is scoped,
where it lives, or how it is rotated. `infra/variables.tf` marks it
`sensitive`, and the S3 backend relies on standard AWS-style env vars
(`infra/main.tf`). That is correct mechanics but does not constitute a
credential-management story.

Concretely, nothing in the proposal answers:

- Is the Vultr API key a full-account root key or a scoped subuser key
  per environment?
- Are `dev`, `staging`, and `production` Terraform applies using the
  same credential, and if so, does that violate the "every environment
  distinct secrets" rule from section 2?
- How are the Object Storage access keys rotated, and who has write
  capability on the state bucket?

Recommendation: add a "Provider credential strategy" subsection to
section 6 (secrets). At minimum require: separate Object Storage access
keys per environment state path, separate Vultr API credentials where
the provider supports scoping, documented rotation cadence, and a
statement that root account credentials are never used for
`tofu apply`.

### 2. Shared benchmark bucket with path-only isolation — MEDIUM

Section 8 stores all benchmark output under
`s3://<benchmark-bucket>/phase1-benchmarks/<env>/...`. A single bucket
shared across `dev`, `staging`, and `production` means a compromised or
mis-permissioned dev runner can overwrite production baselines. The
gate model in section 8 is regression-vs-baseline, so baseline
integrity is load-bearing: if a previous run is silently rewritten,
future regressions are masked.

Path prefixes are not an access-control boundary on Vultr Object
Storage; they are a naming convention.

Recommendation: require either (a) separate buckets per environment,
or (b) per-prefix IAM-style write scoping where the provider supports
it, plus bucket versioning/object-lock so baselines are append-only.
Treat "baseline integrity" as a named audit property with explicit
mitigations, not an implicit consequence of path naming.

### 3. Remote state locking relies on operator discipline — MEDIUM

The proposal acknowledges Vultr Object Storage does not provide native
file locking and states the single-writer rule (section 4, section 13
risk 7). That is honest, but the only mitigation listed is human
discipline. `use_lockfile = true` is set in `infra/main.tf`, but the
effective semantics on a Vultr S3-compatible endpoint are not
established.

For a one-person-plus-agents workflow (AGENTS.md explicitly names
parallel agent work), this is exactly the configuration where two
agents clobber state without noticing.

Recommendation: add a procedural control the proposal can actually
commit to — for example, a wrapper script that acquires an advisory
lock object (PUT-if-absent) in the state bucket before `tofu apply`,
or an explicit statement that Terraform operations always run from a
single operator workstation and never from concurrent agent worktrees.

### 4. VKE control plane exposure and firewall scope not addressed — MEDIUM

Research (`plans/research/phase1-environments-and-benchmarks.md`
question 7) flagged that `enable_firewall` is omitted from
`infra/cluster.tf` and that the VKE Terraform resource supports it.
The proposal discusses Calico and future network policy work
(section 3) but does not address cluster-level firewall scoping at all.

Audit implication: a default VKE cluster exposes a public control
plane endpoint. Without firewall scoping, kubeconfig credential
compromise translates directly to unrestricted `kube-apiserver` access
from any network.

Recommendation: require `enable_firewall = true` (or an explicit,
justified decision to leave it off) with an allowlist for operator
networks and CI egress. Call this out in section 3 alongside the
storage class correction, since both are "Vultr defaults the current
draft failed to engage with."

### 5. Flux bootstrap credential story is absent — MEDIUM

Section 5 describes per-cluster Flux roots and path-based
reconciliation, but not how Flux authenticates to the Git repository.
`flux bootstrap github` requires a GitHub PAT with repo and admin
scopes, and the current `k8s/base/flux-system/gotk-sync.yaml` hardcodes
`https://github.com/nestharus/server-manager.git` — a repo name that
does not match the current working directory, suggesting stale
bootstrap output.

Unspecified:

- Is the bootstrap PAT shared across three clusters or per-cluster?
- Does it rotate?
- Are deploy keys preferred over PATs?
- Who holds it?

Recommendation: require per-cluster deploy credentials (deploy keys or
per-cluster PATs with minimum scope), explicit rotation, and an update
to the bootstrap README that names the correct repo. Re-running `flux
bootstrap` on the correct repo will regenerate `gotk-sync.yaml` and
close the stale-URL loose end.

### 6. Public `dev` load balancer with no TLS/ingress story — MEDIUM

Section 3 allows a public load balancer for `dev` "because it needs
externally reachable E2E and video QA flows," but section 3 also
explicitly leaves the ingress controller out of scope ("does not need
to conflate that with the environment model"). The combination is a
public LoadBalancer Service with no defined TLS termination, no
authentication guidance, and no rate limiting.

Non-production bot tokens and sandbox credentials that live behind
this endpoint are less valuable than production, but they are still
credentials; Playwright recordings and Gemini QA artifacts may
transiently traverse this path.

Recommendation: either defer the public `dev` LB until an ingress
controller with TLS is defined, or constrain Phase 1 `dev` ingress to
a private/allowlisted load balancer until the ingress story lands.
Calling ingress "foundation but out of this phase" while provisioning
a public LB is the audit gap.

### 7. LLM video QA data handling — LOW

Section 9 sends captured videos and structured intent statements to
Gemini. The proposal does not discuss:

- Gemini API key scoping/rotation.
- Data retention at the Gemini endpoint (does data leave the account?).
- Where the captured video artifact is stored and with what ACLs.
- Whether Playwright flows may type credential-shaped values into
  forms that then get recorded.

This is LOW because the workflow is explicitly `dev`-only with sandbox
credentials and non-production Discord identity, which bounds the
blast radius. It should still be named.

Recommendation: add one paragraph to section 9 stating that video
artifacts are stored in the same benchmark bucket under a dedicated
prefix, that the Gemini API key is treated as a per-environment
credential under section 6, and that Playwright test fixtures must
not exercise production-shaped credentials even in `dev`.

### 8. Grafana admin bootstrap writes plaintext to `/tmp` — LOW

`k8s/base/monitoring/grafana-admin-secret.yaml` documents a bootstrap
flow that writes a plaintext Secret to `/tmp/grafana-admin-secret.yaml`
before `kubeseal`. On a shared or multi-tenant workstation this is a
momentary plaintext credential on disk. The proposal inherits this
flow implicitly.

Recommendation: update the bootstrap flow to pipe directly into
`kubeseal` (no `/tmp` intermediate), or require `shred`/unlink after
sealing. Trivial fix; worth stating.

### 9. Storage class correctness — LOW (adequately handled)

The proposal explicitly standardizes on `vultr-block-storage`
(section 3) and names the current `hcloud-volumes` usage as a defect
to fix (sections 3, 7, risk 3). Per-environment PVC sizes in section 7
(Prometheus `10/20/50Gi`, Grafana `10Gi`, Alertmanager `10Gi`) all sit
at or above the documented `10Gi` floor for `vultr-block-storage`.
Research warns that `vultr-block-storage-hdd` has a `40Gi` floor;
since HDD is not the default, sizes are valid.

No action required beyond implementing the section 7 values and
deleting the `hcloud-volumes` references in `k8s/base/monitoring/
helmrelease.yaml`.

### 10. Discord bot isolation — LOW (well handled)

Section 2 and the section 13 risk 5 mitigation are specific and
correct: separate bot tokens, separate Discord applications, separate
sandbox guild ids, no non-production connection to guild
`900000000000000001`. This directly honors AGENTS.md Live Server
Principle and requires no additional audit action.

## Overall assessment

The proposal is substantively sound. Its corrections close the largest
audit defects in the current draft (wrong storage class, ambiguous
Flux topology, cross-environment secret sharing, shared Discord
identity). What keeps the overall verdict at MEDIUM rather than LOW is
that the proposal is silent on six adjacent audit-relevant controls
that a reviewer would reasonably expect a foundation proposal to state
explicitly: provider credential scoping and rotation, benchmark
baseline integrity, remote state locking beyond operator discipline,
VKE control plane firewall posture, Flux bootstrap credential
management, and TLS/ingress on a public `dev` LoadBalancer.

None of these require architectural change. All can be resolved with
targeted additions to sections 4, 5, 6, 8, and 9 plus a statement in
section 3 about firewall scoping.

## What LOW requires

Revise the proposal so that each of the following is stated explicitly,
then re-run the audit gate:

1. Section 6 gains a "Provider credentials" subsection: Vultr API key
   and Object Storage access keys are per-environment, scoped, and
   rotated on a named cadence; root account credentials are never used
   for apply operations.
2. Section 8 names baseline integrity as an audit property and requires
   either per-environment benchmark buckets or versioned/write-once
   baselines with documented ACLs.
3. Section 4 (or a new subsection) specifies a concrete locking control
   for Vultr Object Storage state beyond `use_lockfile` — either an
   advisory-lock wrapper or a single-operator-workstation rule that
   forbids concurrent agent applies against shared state.
4. Section 3 states the VKE firewall posture (`enable_firewall` + IP
   allowlist for operator networks) or justifies the decision to omit
   it.
5. Section 5 specifies per-cluster Flux deploy credentials, their
   scope, and rotation; bootstrap instructions reference the correct
   repository.
6. Section 3 or section 9 resolves the public `dev` LoadBalancer
   exposure: either defer the public LB until an ingress controller
   with TLS is defined, or constrain `dev` ingress to a
   private/allowlisted path for Phase 1.
7. Section 9 names video artifact storage ACLs, Gemini API key
   handling, and a rule against production-shaped credentials in
   Playwright fixtures.
8. Section 6 or the Grafana bootstrap note eliminates the
   plaintext-to-`/tmp` step in the sealed-secret bootstrap.

With those in place, the audit surface is LOW and the risk gate can
pass.
