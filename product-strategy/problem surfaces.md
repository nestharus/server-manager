# Problem Surfaces

New problem surfaces discovered during the problem alignment review. These are gaps in the problem definition, not problems with the proposal.

---

## Proposal-originated Surfaces

### Live configuration safety for in-flight operations

**What the proposal does:** PolicyVersion objects version every configurable policy. When an operator changes a policy, a new version is created and in-flight operations continue under the version active when they started. Form definitions, compliance rules, ticket routing, authority templates, and notification rules are all versioned. The proposal also applies a preview-confirm pattern to configuration changes, showing operators what will change and what in-flight operations will be affected before committing.

**What problem it addresses:** Changing operational rules on a live system while operations are already in progress under the old rules. When an officer modifies an application form mid-review cycle, pending applications could become incoherent if their submitted responses are evaluated against a form definition that no longer matches. When compliance rules change mid-season, evaluations that already ran could become inconsistent with evaluations that haven't. Policy transitions on a live server risk silently altering the meaning of in-progress work.

**Why it's not in the problem definition:** The problem definition touches adjacent concerns: section 4 mentions that audit trails should record "what policy governed the decision," and section 6 mentions compliance criteria are "per-season," implying rules change between seasons. But neither section articulates the specific difficulty: configuration changes on a running system can corrupt the semantic integrity of in-flight operations. Section 4 frames policy versioning as a recording concern (what applied); the proposal reveals it as an operational safety concern (ensuring the right policy applies, and that changes don't retroactively alter in-progress work).

**Evidence it's real:** Communities change their rules regularly — updating application questions, adjusting compliance thresholds between seasons, modifying ticket routing as staff availability shifts. These changes happen while applications are in review, compliance evaluations are running, and tickets are open. Without versioning, a mid-cycle form change could make a submitted application's responses nonsensical against the new field definitions. Without version pinning, a compliance rule update could retroactively invalidate evaluations that already ran correctly under the old parameters. This is a concrete operational hazard that communities face whenever they update their processes.

---

## Emergent Surfaces

### Axis 7: Unmanaged permissions as a distinct drift category

**What the problem definition says:** Discord provides tools to set permissions but no tools to reason about the aggregate effect. There is no native concept of "intended permission state" against which actual state can be audited. Permission drift is described as accumulated unreviewed history — a single phenomenon of decisions compounding over time without systematic review.

**What the proposal reveals:** Once an "intended permission state" system exists, a second category of discrepancy emerges that the problem definition does not distinguish. The proposal's PermissionDrift model identifies drift entries where no matching PermissionIntent exists at all — permissions that were set directly in Discord without going through the management system. These are not permissions that diverged from a declared intent; they are permissions with no declared intent. The proposal surfaces these as "unintended drift requiring classification," a fundamentally different operational response than correcting a known intent that has diverged.

**Why it matters:** The problem definition treats permission drift as one problem: accumulated, unreviewed permission decisions. The proposal reveals it is two problems that require different responses. Drift from a known intent has a clear resolution path — compare actual state to intended state and resolve the discrepancy. Permissions with no declared intent have no resolution path until the operator classifies them — they must first decide whether the permission should exist at all, then create an intent or remove the permission. Conflating these two categories in the problem definition understates the difficulty: introducing an "intended state" system does not automatically bring existing unmanaged permissions into the managed set. The migration of existing permission state into a declared-intent model is itself a significant operational task that the problem definition's description of permission drift does not anticipate.
