# Scope Risk — INIT-009

## Verdict
LOW

## Summary

INIT-009 holds its stated scope. Flux is bounded to the control cluster,
app-cluster Flux is explicitly disclaimed and assigned to INIT-017's
Crossplane Compositions, and the four downstream bases (crossplane,
cert-manager, external-dns, cluster-security) ship as empty README + empty
`kustomization.yaml` stubs that name their owning initiatives. Local-only
enforcement is structural — the SLICE-035 harness must fail on real Vultr
calls, real Cloudflare calls, `tofu apply`, app workload manifests, or
application-cluster Flux roots (proposal.md:644-646). The toolchain
installer is narrowly scoped to `flux/kind/sops/age/age-keygen/kubectl`
plus embedded Kustomize — no `tofu`, `docker`, `helm`, `buildkite-agent`,
or downstream-component CLIs.

Slice boundaries are clean: SLICE-031..036 partition along material axes
(toolchain+disposal, layout, Flux manifests, SOPS, kind harness, docs)
with explicit per-slice anti-scope sections. No slice smuggles INIT-017
through INIT-019 content; no slice crosses into INIT-008's OpenTofu
surface.

The findings below are LOW. The largest is anti-scope completeness:
Section 7 enumerates INIT-010..INIT-014, INIT-017, INIT-018, INIT-019,
but does not explicitly name INIT-015 (Auth), INIT-016 (Observability),
or INIT-020 (Backups) as anti-scope. They are implicit but the user's
rule asks for every other Phase 5 initiative to be called out
explicitly.

## Boundary findings

| ID | Risk type | Severity | Finding | Proposal cite | Recommendation |
|---|---|---|---|---|---|
| SCP-001 | Anti-scope completeness | LOW | §7 enumerates app workloads (INIT-010..014), Buildkite (INIT-011), Crossplane (INIT-017), cert-manager + ExternalDNS (INIT-018), cluster security (INIT-019), but does not explicitly name INIT-015 (Auth), INIT-016 (Observability), or INIT-020 (Backups). They are conceptually subsumed by "application workloads" but the user's rule asks for explicit enumeration of every other Phase 5 initiative. | proposal.md:858-878 | Add three lines to §7: auth-stack manifests (Authentik/OPAL/Pomerium) → INIT-015; observability-stack manifests (logs/metrics/tracing) → INIT-016; backup/restore manifests, snapshot policies, RPO/RTO tooling → INIT-020. |
| SCP-002 | INIT-008 boundary overlap | LOW | SLICE-036 updates `infra/README.md` (proposal.md:660-693, hookpoints §5 lines 798-801). INIT-008 owns `infra/`. INIT-008 is "complete (local); PR open deferred" per PHASE_5_INDEX. The change as described is stale-reference removal + cross-link to `gitops/`, which is reasonable, but SLICE-036 anti-scope does not explicitly disclaim re-authoring INIT-008 channel content. | proposal.md:660-693, 798-801 | Add to SLICE-036 anti-scope: "no rewrite of INIT-008 channel-registry content; only stale `infra/environments/{dev,staging,production}` reference removal and a one-line cross-link to `gitops/`." |
| SCP-003 | Empty-placeholder discipline | LOW | The dev overlay composes four empty bases (proposal.md:192-198). Each base ships only `README.md` + empty `kustomization.yaml` (§2.3 lines 168-186; SLICE-032 file list 488-496). The contract is correctly stated as "early resource additions a scope violation" (line 186), but `validate_gitops.sh --layout-only` does not include a programmatic guard preventing a future PR from quietly adding `resources:` to these bases. | proposal.md:168-186, 192-198, 502-520 | Add to SLICE-032 / §6 AC: "`validate_gitops.sh --layout-only` asserts `gitops/bases/{crossplane,cert-manager,external-dns,cluster-security}/kustomization.yaml` contains no `resources:` entries and that owner-naming README is present." Promotes prose discipline to test failure. |
| SCP-004 | INIT-018 structural pre-split | LOW | The proposal pre-splits INIT-018 into two distinct empty bases — `gitops/bases/cert-manager/` and `gitops/bases/external-dns/` (proposal.md:128-133, 177-179, 491-494). This is a one-way structural call made on INIT-018's behalf. INIT-018 may prefer a combined or differently-named base. Boundary integrity is preserved (both are empty + owner-named), but layout authority over INIT-018 is mildly pre-empted. | proposal.md:128-133, 177-179, 491-494 | Optional, non-blocking: SLICE-036 docs note that INIT-018 may collapse, rename, or restructure these two bases at its discretion. |
| SCP-005 | Two-tier discipline | NONE | §2.1 says Flux on this control cluster "does not reconcile `services/api`, `services/discord`, CloudNativePG, app-cluster ingress, app-cluster auth, or app-cluster observability." §2.4: "The overlay does not include an application-cluster root." §2.7: "not one Kustomization per future app cluster." SLICE-033 ACs require validation that "no Flux Kustomization path points at application workloads or app-cluster roots." Multi-cluster Flux federation is in §7 anti-scope. | proposal.md:105-111, 207-209, 277-279, 555-558, 870-871 | None — line is held cleanly. |
| SCP-006 | Local-only adherence | NONE | §2.10 forbids real Vultr/Cloudflare/`tofu apply`/image push/public Git. §2.5 requires the local Git source to come from the worktree, not GitHub. SLICE-035 harness includes a fail-condition for "real Vultr calls, real Cloudflare calls, `tofu apply`, app workload manifests, or application-cluster Flux roots" (line 645-646). Bootstrap script generates a local age key written outside the repo (§2.9 line 377-380). | proposal.md:225-235, 386-394, 644-646 | None. |
| SCP-007 | Toolchain installer scope | NONE | §2.10 fixes the tool list to `flux`, `kind`, `sops`, `age`, `age-keygen`, `kubectl`, embedded Kustomize. SLICE-031 anti-scope: "no Flux manifests, no SOPS policy, no kind cluster creation, no macOS/Windows installer parity, no `k8s/` wrapper." Installer does not creep into `tofu`, `docker`, `helm`, `buildkite-agent`, or downstream-component CLIs. `kubectl` overlaps with INIT-008 toolchain but is essential for `kubectl kustomize` rendering and idempotent. | proposal.md:396-411, 473-474 | None. |
| SCP-008 | SOPS+age scope | NONE | Per-channel recipients only (proposal.md:319-322, 422). Rotation tooling is anti-scope (§2.9 lines 343-345; §7 line 873; SLICE-034 anti-scope line 605). Multi-operator key management is anti-scope (line 874). Bootstrap may generate a local age key; private key is operator-local and never committed. | proposal.md:319-380, 605-607, 873-874 | None. |
| SCP-009 | Same-repo Flux source | NONE | Flux reads from this `server-manager` repo (§2.5). Mitigation is documented: a hard root-level `gitops/` boundary, validation that Flux paths stay under `gitops/channels/dev`, and no external GitOps repo until a later deployment initiative explicitly proposes one (§4 line 723-728). The local harness uses an in-cluster Git source seeded from the worktree, avoiding public-Git dependence. | proposal.md:211-235, 722-728 | None — this is a tradeoff, accepted with documented mitigation. |
| SCP-010 | Channel-overlay carries verification-only patch | LOW | `gitops/channels/dev/patches/flux-source-local.yaml` overrides the GitRepository URL for local kind verification and lives inside the channel overlay (§2.4 line 142-145, §2.5 line 226-228). INIT-017+ that extend the `dev` channel will inherit a channel that carries a "local-only" patch. Risk is structural ambiguity, not boundary leakage — the channel is the control-cluster-local one and Phase 5 verification is its only execution surface. | proposal.md:142-145, 226-228, 540-541 | Optional, non-blocking: SLICE-033/036 could note whether this patch is conditionally composed (e.g., separate `kustomization-local.yaml`) or remains an immovable channel artifact for future deployment initiatives to handle. |

## Slice-boundary judgement

Six slices, clean DAG (proposal.md:696-708):

- **SLICE-031** (toolchain + `k8s/` deletion) — correctly the entrypoint; no Flux/SOPS/kind work. Anti-scope explicitly excludes Flux manifests, SOPS policy, and kind cluster creation.
- **SLICE-032** (layout + empty bases + dev overlay shell) — paths only, no payloads. Anti-scope excludes controller payloads, app workloads, and additional active channels.
- **SLICE-033** (Flux manifests + dev channel root) — the only slice that ships active Flux content. Anti-scope excludes app-cluster Flux, Crossplane install, Helm repos, real remote credentials.
- **SLICE-034** (SOPS+age) — secret workflow only. Anti-scope excludes rotation tooling, multi-operator workflow, real Discord/Vultr/Cloudflare credentials, sealed-secrets.
- **SLICE-035** (kind harness) — integrates SLICE-031..034 end-to-end. Anti-scope excludes real VKE bootstrap, external Git hosting dependency, app-cluster provisioning, image push, workload deployment.
- **SLICE-036** (docs + stale-material disposal) — doc-only. Anti-scope excludes new research, downstream manifests, real-deployment runbook, production channel.

The one shared file across slices is `gitops/tests/validate_gitops.sh`,
which each slice extends with its own assertions (`--layout-only`,
`--flux-render-only`, `--sops-only`, full `--cluster`, `--docs-only`).
This is appropriate because the harness is the cross-cutting acceptance
surface.

SLICE-032 and SLICE-033 both touch
`gitops/bases/flux-system/kustomization.yaml`: SLICE-032 creates the file
shell, SLICE-033 populates it. The split is intentional and documented
(layout vs. content). No slice smuggles INIT-017/018/019 content; no
slice crosses into INIT-008's OpenTofu surface.

SLICE-033 and SLICE-034 are correctly parallelizable after SLICE-032
because Flux manifests and SOPS policy live in disjoint subtrees
(`gitops/bases/flux-system/` vs `gitops/secrets/dev/`).

## Convergence statement

INIT-009 stays inside its stated scope. The control-cluster-only
constraint holds across architecture (§2.1), slice scopes, anti-scope
(§7), and acceptance criteria (§6). Empty downstream bases are framed
as authorized handoff seams under `~/ai/conventions/no-deferred-stubs.md`
(proposal.md:21-24, 184-186) — owner-named, with prose forbidding early
resource additions.

Three small, non-blocking adjustments would tighten the boundary
further:

1. **SCP-001:** Add INIT-015, INIT-016, INIT-020 to §7 anti-scope explicitly.
2. **SCP-002:** Add a one-line SLICE-036 anti-scope clarifying that `infra/README.md` updates are stale-reference removal + cross-link only, not INIT-008 channel content reshaping.
3. **SCP-003:** Promote the empty-base discipline from prose to a `validate_gitops.sh --layout-only` assertion that fails on any `resources:` in the four downstream bases.

None of these block the proposal. Scope risk is **LOW** and the proposal is
cleared on this dimension.
