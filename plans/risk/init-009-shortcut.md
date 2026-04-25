# Shortcut Risk — INIT-009

## Verdict
LOW

## Summary

The INIT-009 proposal is purpose-fit. Its design choices read as principled
rather than corner-cutting: Flux self-manages from Git, SOPS+age is mandatory
with per-channel recipients, the legacy `k8s/` tree is deleted (not aliased
or shimmed), empty downstream bases are documented handoff seams owned by
named successor initiatives (INIT-017/018/019), and local verification is
treated as the design property rather than a "good enough for now" stand-in.
The single `kubectl apply` use in `bootstrap-flux.sh` is the standard Flux
seed step with explicit handoff to Flux-owned reconciliation afterward, not a
manual override. Cadences (`1m` source / `5m` Kustomization, `prune: true`,
`wait: true`) are tight enough to expose drift. The toolchain installer
pins versions per Section 2.10 and the proposal acknowledges the Linux-first
OS-coupling rather than papering over it.

The proposal openly invites risk-gate scrutiny on five observations
(Section 9): local Git source complexity, installer network access for tool
acquisition, empty-base handoff seams, single active `dev` channel, and
INIT-017's app-cluster Flux ownership. All five are honest framings of
design tradeoffs, not rationalizations of shortcuts.

The findings below are LOW-severity tightening notes that the implementation
phase should pin down. None are fake-completion or hidden-compromise risks
that would gate proposal approval; they should fold into the SLICE-031,
SLICE-034, SLICE-035, and SLICE-036 acceptance contracts so the shortcut
surface stays closed at implementation time.

## Findings table

| ID | Type | Severity | Finding | Proposal cite | Recommendation |
|---|---|---|---|---|---|
| SH-1 | hardcoded | LOW | Section 2.10 pins tool versions but neither §2.10 nor SLICE-031 names authoritative download sources. An installer that resolves `flux`/`kind`/`sops`/`age` via `curl \| bash` from arbitrary URLs would still meet the `--check` contract while introducing a supply-chain shortcut. | `.pipeline/proposal.md:380-410, 444-468` | SLICE-031 must constrain acquisition to (a) the tool's official release tarball with SHA256 verification, (b) a Linux distro package manager, or (c) `go install` from a pinned module proxy. The installer header should list the exact download URLs and checksums. |
| SH-2 | workaround | LOW | `bootstrap-flux.sh` "Create or reuse the kind cluster" (§2.6 step 1, §3 SLICE-035). Reusing a pre-existing kind cluster could carry leftover Flux/Kustomization objects from prior runs and let `flux check` pass against stale state, masking failures a fresh bootstrap would expose. | `.pipeline/proposal.md:251-252, 547-554, 614-624` | SLICE-035 should make fresh-cluster the default (`--cluster` creates if absent, errors if present unless `--reuse` is passed) so reuse is opt-in. `validate_gitops.sh` should assert no foreign Flux objects are present before declaring green when `--reuse` is in effect. Document that `--reuse` weakens the proof. |
| SH-3 | coupling | LOW | D12 closure says "implementation consumes or mirrors INIT-008 `dev` channel input." "Mirror" — read as "drop a copy into this worktree" — risks a fixture that decouples from INIT-008's channel registry as it evolves and silently goes stale. | `.pipeline/proposal.md:208-209, 416-417, 459-462` | SLICE-032 should consume INIT-008's `infra/channels/dev.yaml` by branch dependency (rebase/merge) rather than copying. If a transient fixture is unavoidable, mark it with a delete-on-merge invariant test, not a static copy. |
| SH-4 | hardcoded | LOW | §2.9 `.sops.yaml` example shows `age: age1...` as the recipient. If the literal placeholder string is committed, the SOPS policy is a non-functional fixture and the "encrypted" sample is unencryptable/undecryptable in CI. | `.pipeline/proposal.md:331-336` | `bootstrap-flux.sh` (SLICE-034) must write the operator-supplied or freshly-generated public recipient into `gitops/secrets/dev/.sops.yaml` before commit. The acceptance test must `sops --decrypt` the sample, which would fail against `age1...` and force the real recipient to land. |
| SH-5 | shim | LOW | `gitops/secrets/dev/bootstrap-creds.enc.yaml` is named "bootstrap-creds" but is a fixture (proposal:594-595 allows "deterministic fixture"). The naming invites a future contributor to drop real bootstrap credentials in there, treating the verification fixture as the production secret slot. | `.pipeline/proposal.md:148, 499, 593-600` | Rename to `sample-secret.enc.yaml` or `verification-fixture.enc.yaml`, and have `gitops/secrets/dev/README.md` state the file is a SOPS proof fixture and not the slot for real credentials. Real bootstrap credentials are an INIT-017/018 concern. |
| SH-6 | fake-completion | LOW | §2.6 step 9 "smoke reconcile of the empty downstream bases" — if `gitops/bases/{crossplane,cert-manager,external-dns,cluster-security}/kustomization.yaml` is `resources: []`, Flux marks the Kustomization "ready" trivially. The harness needs to assert the *path* was actually evaluated against the current source SHA, not just that the Kustomization is green. | `.pipeline/proposal.md:258-259, 612, 614-624` | `validate_gitops.sh` should assert `flux get kustomizations` lists each empty-base path and that `kubectl describe kustomization <name>` shows a non-zero applied-revision matching the test source SHA. The harness wording should distinguish "Flux source + dev-control root reconciled" (load-bearing) from "downstream-base composition rendered with zero resources" (composition smoke). |
| SH-7 | deferred | LOW | Empty downstream bases (§2.3) declare "early resource additions a scope violation" but no test enforces this beyond README convention. A future contributor could add Crossplane manifests under `gitops/bases/crossplane/` without tripping any check, voiding the no-deferred-stubs guard at runtime. | `.pipeline/proposal.md:175-186, 421-440, 510-512, 681-685` | SLICE-032 layout validation (`validate_gitops.sh --layout-only`) should assert each empty base contains only `README.md` and `kustomization.yaml`, and that the latter has empty `resources:` until the owning INIT lands. The check enforces the contract the README declares. |
| SH-8 | coupling | LOW | The local Git source seeding strategy is left open ("an in-cluster Git service seeded from `git bundle`, a local container reachable from kind, or another Flux-compatible local HTTP Git endpoint"). If SLICE-035 picks a fragile approach (e.g., a host-mounted bare repo that drifts from the worktree), the local-only proof becomes flaky and the temptation to fall back to a public Git URL re-emerges. | `.pipeline/proposal.md:227-235, 614-624` | SLICE-035 should lock one mechanism (recommend: in-kind `gitserver` pod fed by `git bundle create` from the current worktree, then `GitRepository.url: http://gitserver.flux-system.svc/...`) and `validate_gitops.sh` should assert the Flux `GitRepository.url` resolves to a cluster-internal hostname, never `github.com` or any public host. |
| SH-9 | deferred | LOW | Stale-material disposition for `plans/proposals/gitops-foundation.md` is "revise and banner-mark in SLICE-036 **unless hookpoints determine full deletion is cleaner**" (proposal:887-889). The conditional defers the keep-vs-delete call to implementation. A banner that sits on top of contradictory environment-triad content still leaves stale guidance live. | `.pipeline/proposal.md:586-604, 707-725, 808-862, 887-889` | SLICE-036 must complete the surgery: either the listed "keep" concepts are extracted into a brief evergreen note and the original is deleted, or the original is rewritten and the contradictory sections (environment-triad roots, app-cluster Flux ownership, "INIT-009 does not write Flux manifests") are physically removed. A banner without removing the contradictions is the shortcut. |
| SH-10 | deferred | LOW | The Flux `GitRepository.ref.branch` is "the branch under test or the branch configured by the bootstrap script." For local verification this is reasonable, but the proposal does not require the bootstrap script to derive the branch from `git rev-parse --abbrev-ref HEAD` of the seeded worktree. A hard-coded `main` would silently reconcile the wrong tree on a feature branch. | `.pipeline/proposal.md:222-225, 481-482, 614-624` | SLICE-035 should derive the branch from the worktree being bundled and assert post-reconcile that the commit hash Flux reports matches `git rev-parse HEAD` of the seeded source. |

## Convergence statement

INIT-009 is purpose-fit and not relying on shortcuts to claim done-ness. Its
local-only proof surface, Flux self-management contract, per-channel SOPS+age
custody, version-pinned toolchain, and clean deletion of the legacy `k8s/`
tree all align with the stated purpose of standing up the GitOps substrate
for the control cluster without anticipating INIT-017/018/019. Empty
downstream bases are authorized handoff seams under no-deferred-stubs because
each names a successor initiative — not silent stubs. The five risk-gate
observations the proposal itself flagged are accurate and the design holds
up against them.

The ten LOW findings above are implementation-phase tightening, not proposal
defects: pin install sources and checksums (SH-1), make kind reuse explicit
opt-in (SH-2), prefer branch-dependency over channel-fixture mirroring
(SH-3), ensure the committed `.sops.yaml` carries a real recipient (SH-4),
rename the fixture so it cannot be mistaken for a production credential slot
(SH-5), make the empty-base smoke reconcile assert evaluation occurred
(SH-6), add a layout invariant that enforces the empty-base contract (SH-7),
lock the local Git source mechanism and assert no public host (SH-8),
complete the stale-material surgery rather than banner-marking on top of
contradictions (SH-9), and derive Flux's source branch from the seeded
worktree (SH-10). None of these findings gate proposal approval; they are
notes the slice authors should fold into acceptance harnesses during
SLICE-031..SLICE-036 implementation.

Risk-gate verdict: proceed.
