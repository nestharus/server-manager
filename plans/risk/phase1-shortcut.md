# Risk assessment — Phase 1 Foundation Bootstrap

## Overall verdict: LOW

The proposal is disciplined and narrow. It stays within locked decisions,
avoids competing mutation paths, does not introduce throw-away patterns,
and is transparent about its limitations. The findings below are minor
under-specifications of acknowledged details, not hidden structural
risks.

## Findings

### 1. Packer bootstrap seam is acknowledged but under-specified — LOW

The proposal's exit criteria require "OpenTofu can create the Hetzner
substrate and the kube-hetzner bootstrap from a clean environment." The
research shows that `kube-hetzner` requires a Packer-built MicroOS
snapshot before `tofu apply` can run. That step lives outside the
OpenTofu resource graph.

The proposal acknowledges this seam in Section 3 ("Kubernetes substrate")
and Section 6 ("Risks"), but it does not specify how the Packer step is
captured in the reproducibility story. The risk is not that the seam
exists — it is inherent to `kube-hetzner` — but that "reproducible from
clean" could quietly mean "reproducible after an operator manually runs
Packer," which is the kind of undocumented manual step the proposal says
it wants to avoid.

**Severity**: LOW. The seam is visible, not hidden. The exit criteria
should make the Packer step explicit rather than implicit.

### 2. Age key custody is flagged but not resolved — LOW

SOPS with `age` is a sound bootstrap secrets choice. The proposal
correctly identifies key custody as a high-leverage failure point
(Section 6, Risks). However, it does not address the concrete bootstrap
question: who holds the age private key, how is it distributed to
operators and to Flux, and how is it backed up before the rest of the
platform exists?

This is not a shortcut — SOPS + age is a legitimate long-term pattern,
not a stopgap. The gap is that the proposal treats key custody as a risk
to monitor rather than a bootstrap detail to resolve during Phase 1.

**Severity**: LOW. The pattern is sound. The operational procedure for
key distribution should be addressed during implementation, not deferred
past Phase 1.

### 3. Secondary provider path for object storage — LOW

The proposal acknowledges that Hetzner S3-style object storage is not
covered by the `hcloud` provider and "may rely on a secondary provider
path." The research confirms this requires a MinIO or S3-compatible
provider alongside `hcloud`.

This is a minor control-path split within OpenTofu, not a competing
mutation path. Both providers run through the same `tofu apply`. The
risk is cosmetic fragmentation, not architectural divergence.

**Severity**: LOW. Document the dual-provider graph explicitly so it
does not surprise operators who expect a single-provider story.

### 4. No shortcut replacement detected — PASS

The proposal does not swap one shortcut for another. Every component
choice (`kube-hetzner`, SOPS + age, Kong, Flux, Hetzner Object Storage)
is either a locked decision or a well-researched bootstrap-appropriate
selection. The proposal is explicit about what each choice does and does
not solve.

### 5. No hidden deferrals detected — PASS

Deferred systems (Authentik, OPAL/Cedar, Pomerium, Smallstep, Postgres)
are listed in Section 5 with clear reasoning. Open questions (Section 6)
are stated as open, not quietly assumed away. The proposal does not
pretend that deferral eliminates the work.

### 6. No temporary ingress or secrets patterns — PASS

Kong is the locked ingress decision, not a placeholder. SOPS + age is a
production-grade GitOps secrets pattern that can serve indefinitely, not
a throwaway bridge to a "real" secrets system. Neither requires
immediate replacement after Phase 1 completes.

### 7. No duplicate control paths — PASS

The Buildkite/Flux boundary is explicitly defined: Buildkite owns CI,
Flux is the sole cluster reconciler, Git is the source of truth. The
proposal's strongest architectural contribution is preventing the most
common bootstrap failure — two competing mutation paths.

## Recommendations

No blocking recommendations. The following would strengthen the
proposal but are not required to proceed:

1. **Make the Packer step explicit in exit criteria.** Change "OpenTofu
   can create the Hetzner substrate and the kube-hetzner bootstrap from
   a clean environment" to include the Packer image-build step as a
   documented pre-requisite, not an implicit operator assumption.

2. **Resolve age key custody during Phase 1 implementation.** Document
   who generates the age keypair, where the private key is stored, how
   Flux receives decryption access, and what the backup/recovery path
   is. This does not need to be in the proposal itself, but it should be
   a Phase 1 implementation deliverable, not a post-Phase 1 concern.

3. **Document the dual-provider OpenTofu graph.** Note explicitly that
   the Hetzner infrastructure state includes both `hetznercloud/hcloud`
   and a secondary S3-compatible provider for object-storage buckets, so
   the operator model is clear from day 1.
