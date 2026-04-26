# Audit Risk — INIT-101

## Verdict
LOW

## Summary

The proposal satisfies the audit checklist for INIT-101. It defines a clean
k3s-shaped channel contract, removes VKE-shaped fields and active artifacts,
keeps local k3d as the done-state deployment proof, limits remote work to
validation and plan-only checks, and covers all six slices with executable
acceptance checks and explicit anti-scope.

No checklist item is PARTIAL or MISSING on a load-bearing artifact.

## Findings table

| ID | Category | Severity | Finding | Proposal cite | Recommendation |
| --- | --- | --- | --- | --- | --- |
| None | N/A | N/A | No audit findings. | N/A | N/A |

## Coverage matrix

| Checklist item | Status | Proposal cite | Notes |
| --- | --- | --- | --- |
| Channel schema additions for k3s defined: `cluster.distribution`, `k3s_version`, `target`, servers/agents config | PRESENT | `.pipeline/proposal.md:185-198`, `.pipeline/proposal.md:209-218` | Required k3s replacement fields and local/dev channel values are named. |
| Schema versioning posture: `schema_version: 1` stays; v2 reserved for future | PRESENT | `.pipeline/proposal.md:176-183`, `.pipeline/proposal.md:721-724` | Proposal keeps schema version `1`, accepts only `1`, and rejects supporting v1/v2 side by side. |
| `additionalProperties: false` enforced | PRESENT | `.pipeline/proposal.md:199-202` | Required everywhere unless explicitly documented open. |
| VKE-shaped fields explicitly removed | PRESENT | `.pipeline/proposal.md:280-282`, `.pipeline/proposal.md:357-359`, `.pipeline/proposal.md:822-826`, `.pipeline/proposal.md:887-909` | VKE fields, module names, tfvars, aliases, readers, and examples are removed or barred. |
| `platform-cluster-vms` variables enumerated with types and default/required status | PRESENT | `.pipeline/proposal.md:284-299` | Variable contract table lists type and default or required status. |
| `platform-cluster-k3d` variables enumerated with types and default/required status | PRESENT | `.pipeline/proposal.md:248-261` | Variable contract table lists type and default or required status. |
| Template module call explicit conditional based on `cluster.target` | PRESENT | `.pipeline/proposal.md:333-359`, `.pipeline/proposal.md:827-828` | `k3d-local` dispatches to k3d; `vultr-vms` dispatches to network plus VM modules. |
| Cloud-init template pinned k3s install version and idempotent | PRESENT | `.pipeline/proposal.md:300-332`, `.pipeline/proposal.md:829-831` | `INSTALL_K3S_VERSION` is set from the pinned input and idempotency guards are contractually required. |
| Real k3d cluster created at done-state | PRESENT | `.pipeline/proposal.md:50-53`, `.pipeline/proposal.md:470-482`, `.pipeline/proposal.md:800-802` | Proposal requires a real `humility-local` cluster. |
| kubeconfig retrieved and usable | PRESENT | `.pipeline/proposal.md:360-384`, `.pipeline/proposal.md:810-814` | Channel-scoped kubeconfig path and `kubectl` use are specified. |
| `kubectl get nodes` returns >= 1 node assertion in harness | PRESENT | `.pipeline/proposal.md:473-475`, `.pipeline/proposal.md:656-675`, `.pipeline/proposal.md:812-814` | Harness and slice AC assert node count. |
| Bring-up and tear-down scripts idempotent | PRESENT | `.pipeline/proposal.md:412-445`, `.pipeline/proposal.md:540-555`, `.pipeline/proposal.md:656-675` | Double bring-up and double tear-down are required no-op/idempotency checks. |
| `tofu validate` clean for bootstrap state-backend root | PRESENT | `.pipeline/proposal.md:456-457`, `.pipeline/proposal.md:815` | Bootstrap state-backend validation is in the harness and INIT AC. |
| `tofu plan` clean against dev channel root in k3s shape | PRESENT | `.pipeline/proposal.md:467-469`, `.pipeline/proposal.md:584-592`, `.pipeline/proposal.md:818-821` | Dev plan is required when credentials and required remote inputs are present; missing credentials skip only remote plan. |
| No `tofu apply` invoked anywhere in proposal | PRESENT | `.pipeline/proposal.md:584-596`, `.pipeline/proposal.md:854-856` | Slice commands use plan only; anti-scope bars remote apply and remote deployment. |
| INIT-008 VKE-shaped artifact deletion named in a slice | PRESENT | `.pipeline/proposal.md:489-522` | Slice 101.01 deletes or rejects active VKE material. |
| No `archived/` subdirectory or compatibility shim | PRESENT | `.pipeline/proposal.md:163-166`, `.pipeline/proposal.md:520-522`, `.pipeline/proposal.md:735-737`, `.pipeline/proposal.md:864-869`, `.pipeline/proposal.md:907-909` | In-tree archives, aliases, readers, forwarding modules, and compatibility examples are rejected. |
| Reference branches preserved | PRESENT | `.pipeline/proposal.md:163-166`, `.pipeline/proposal.md:882-886` | Reference copy stays on `feat/init-008-platform-bootstrap` and its worktree. |
| Each of 6 slices has explicit ACs | PRESENT | `.pipeline/proposal.md:489-709` | All six slices include acceptance criteria. |
| Each AC is locally executable | PRESENT | `.pipeline/proposal.md:506-512`, `.pipeline/proposal.md:539-550`, `.pipeline/proposal.md:576-588`, `.pipeline/proposal.md:619-632`, `.pipeline/proposal.md:656-669`, `.pipeline/proposal.md:694-699` | Each slice lists local verification commands; remote plan is locally executable when credentials are present. |
| Dependency DAG is acyclic | PRESENT | `.pipeline/proposal.md:518`, `.pipeline/proposal.md:556`, `.pipeline/proposal.md:593`, `.pipeline/proposal.md:639`, `.pipeline/proposal.md:677`, `.pipeline/proposal.md:705` | Dependency chain is `101.01 -> 101.02/101.03 -> 101.04 -> 101.05 -> 101.06`. |
| Anti-scope per slice | PRESENT | `.pipeline/proposal.md:520-522`, `.pipeline/proposal.md:558-559`, `.pipeline/proposal.md:595-596`, `.pipeline/proposal.md:641-643`, `.pipeline/proposal.md:679-680`, `.pipeline/proposal.md:707-709` | Each slice has an anti-scope clause. |
| k3s version pinned | PRESENT | `.pipeline/proposal.md:29-31`, `.pipeline/proposal.md:305-323`, `.pipeline/proposal.md:398`, `.pipeline/proposal.md:802` | `v1.32.13+k3s1` is pinned. |
| k3d version pinned | PRESENT | `.pipeline/proposal.md:31-32`, `.pipeline/proposal.md:397-411`, `.pipeline/proposal.md:541-551`, `.pipeline/proposal.md:801` | `v5.8.3` is pinned. |
| Vultr provider version pinned | PRESENT | `.pipeline/proposal.md:36-37`, `.pipeline/proposal.md:392-396` | Vultr provider remains constrained to `~> 2.30`. |
| OpenTofu version pinned to `1.11.5` | PRESENT | `.pipeline/proposal.md:385-391`, `.pipeline/proposal.md:805-806` | Proposal, harness, and operator docs verify OpenTofu CLI `1.11.5`. |
| Lockfile expectation stated | PRESENT | `.pipeline/proposal.md:462-466`, `.pipeline/proposal.md:610-636`, `.pipeline/proposal.md:834-835` | Root lockfiles are committed and drift-free; modules do not carry provider lockfiles. |
| HA explicitly deferred to named successor | PRESENT | `.pipeline/proposal.md:711-715`, `.pipeline/proposal.md:870-879` | HA is named as INIT-118. |
| Single-server posture documented as bounded | PRESENT | `.pipeline/proposal.md:71-76`, `.pipeline/proposal.md:271-279`, `.pipeline/proposal.md:589-596`, `.pipeline/proposal.md:847-856` | INIT-101 is bounded to single remote server plan surface and no remote deployment. |
| No deferred stub language for HA | PRESENT | `.pipeline/proposal.md:870-880` | Named successors are explicit scope boundaries, not stubs. |
| Need to install k3d locally; named installer step | PRESENT | `.pipeline/proposal.md:403-411`, `.pipeline/proposal.md:531-554`, `.pipeline/proposal.md:795-796`, `.pipeline/proposal.md:803-804` | `infra/scripts/install-cluster-tools.sh` owns pinned k3d install/check behavior. |
| Installer pins versions | PRESENT | `.pipeline/proposal.md:403-411`, `.pipeline/proposal.md:803-804` | Installer pins k3d to `v5.8.3` and rejects floating `latest`. |

## Convergence statement

The audit gate converges to LOW. Every requested checklist item is PRESENT in
the proposal, local-as-first-deployment remains the completion bar, remote work
is plan-only, and no load-bearing artifact is PARTIAL or MISSING.
