# Shortcut risk assessment — Phase 1 Foundation Bootstrap

**Proposal:** `plans/proposals/phase1-foundation.md`
**Date:** 2026-04-14
**Overall verdict:** LOW

## Criterion 1 — Does the proposal replace one shortcut with another?

**Severity: NONE**

No shortcut-for-shortcut swaps detected. Each component choice in the
proposal traces back to a locked decision or a research-backed
recommendation, not to an expedient workaround replacing a prior one.

- `kube-hetzner` replaces custom VM-and-script assembly with a mature,
  opinionated module (v2.19.2, production-ready defaults). That is a
  deliberate scope reduction, not a shortcut.
- `SOPS + age` replaces "no secrets workflow" with a GitOps-native
  bootstrap path. It is a legitimate long-term option, not a temporary
  hack that merely defers the problem.
- `Hetzner Object Storage` via a secondary provider (MinIO) is
  acknowledged openly in the research. The proposal does not pretend the
  `hcloud` provider covers it.

## Criterion 2 — Does it hide unresolved bootstrap complexity behind vague deferrals?

**Severity: LOW**

The proposal is forthright about what it defers (Postgres placement,
Buildkite agent location, secrets evolution, Pomerium timing, Smallstep
timing). Each deferral is listed as an explicit open question with a
rationale for why it does not belong in Phase 1.

Two minor areas deserve attention but do not reach MEDIUM:

1. **kube-hetzner Packer seam.** The OpenTofu research notes that
   `kube-hetzner` requires a Packer image-build step before
   `tofu apply`. The proposal's scope section says "bootstrap k3s
   through kube-hetzner" and the exit criteria require creating the
   cluster "from a clean environment," but the Packer step is not
   enumerated as a deliverable or documented seam. Risk is that the
   image build becomes an undocumented operator ritual.

2. **Object storage provider boundary.** The proposal says "some
   Hetzner object-storage handling may rely on a secondary provider path
   until the implementation details are finalized." The phrase "until
   finalized" is vague, but the research already identifies the MinIO
   provider as the concrete path. The implementation phase should pin
   this rather than leave it floating.

Neither item conceals complexity that would block the bootstrap. Both
are addressable during implementation planning.

## Criterion 3 — Does it introduce a temporary secrets or ingress pattern that will immediately need replacement?

**Severity: NONE**

- **SOPS + age** is not a throwaway. It is a production-grade
  GitOps-native secrets workflow used widely in Flux-based stacks. The
  proposal correctly frames it as the bootstrap default that "later
  phases can replace or augment." It does not promise replacement; it
  permits evolution. No immediate rip-and-replace is implied.
- **Kong** is the locked ingress layer, not a temporary stand-in. Its
  Phase 1 role (north-south traffic) is a subset of its permanent role,
  not a different pattern.
- **Operator access without Pomerium** is the natural state of a
  bootstrap cluster, not a temporary ingress pattern. Pomerium
  introduction in a later phase adds a layer; it does not replace the
  access model.

## Criterion 4 — Does it duplicate platform control paths or create operator-only manual seams?

**Severity: LOW**

- **CI/CD boundary** is explicitly designed to prevent dual mutation
  paths. The proposal states this as a hard architectural boundary:
  Buildkite owns CI, Flux is the sole reconciler, and Buildkite does
  not perform out-of-band cluster mutation. This is the cleanest finding
  in the assessment.
- **OpenTofu + kube-hetzner** is a designed module seam within a single
  IaC graph, not competing control planes.
- **Packer image build** is the one semi-manual step that sits outside
  the `tofu apply` path. It is inherent to the kube-hetzner module, not
  introduced by the proposal. The exit criteria's "from a clean
  environment" clause provides implicit coverage, but the implementation
  should automate or document this step explicitly to prevent it from
  becoming an operator-only ritual.
- **Two OpenTofu providers** (`hcloud` + MinIO for object storage) is
  standard multi-provider practice, not a duplicated control path.

## Summary

| Criterion | Severity |
| --- | --- |
| Shortcut-for-shortcut swap | NONE |
| Hidden bootstrap complexity | LOW |
| Temporary secrets/ingress pattern | NONE |
| Duplicated control paths / manual seams | LOW |
| **Overall** | **LOW** |

The proposal is well-scoped, honest about its boundaries, and does not
introduce shortcuts. No recommendations are required to change the
proposal's direction. Two minor items should be addressed during
implementation planning:

1. Enumerate the kube-hetzner Packer image-build step as a documented
   part of the bootstrap sequence and include it in the rebuild story.
2. Pin the object storage provider path (MinIO provider for bucket
   automation) rather than leaving it as "to be finalized."
