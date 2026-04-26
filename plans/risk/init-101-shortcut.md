# Shortcut Risk — INIT-101

## Verdict
LOW

## Summary

The proposal substantively honors the governing environment-agnostic
principle. Local and remote channels share the same k3s distribution
(`v1.32.13+k3s1`, D1) and the same channel-template dispatcher; there is no
"local-only" parallel template, no kind/minikube/Compose escape hatch, and
no `vultr_kubernetes` resurrection. The local channel is a real first
deployment, not a verification surrogate: `bring-up-local-channel.sh` creates
a real k3d cluster, writes a channel-scoped kubeconfig, and the harness
asserts `KUBECONFIG=...kubeconfig.yaml kubectl get nodes` returns a real
node count (proposal §2.11 lines 412-426; §2.12 lines 470-477; §6 acceptance
lines 800-815). Skipping local cluster creation is explicitly forbidden
(§2.12 lines 481-482; SLICE-101.05 anti-scope line 680).

VKE disposal is hard-delete with no `archived/`, `legacy/`, symlink,
forwarding module, deprecated alias, or dual schema reader (§2.2 lines
156-166; §8 lines 882-909). SLICE-101.01 includes a grep invariant
that fails the slice if any of `vultr_kubernetes`, `kubernetes_version`,
`node_pools`, `ha_controlplanes`, or managed-cluster `enable_firewall`
re-enters `infra/` (lines 510-512). Tradeoff #3 explicitly justifies why
`schema_version` remains `1` rather than introducing a v1+v2 dual reader —
this is consistent with `no-backwards-compatibility.md`, not in tension
with it, because the wrong-shaped VKE reader never becomes the accepted
main-path contract.

The asymmetry "local must be real, remote stays plan-ready" (Tradeoff #2,
lines 717-720) is **not** a local-vs-remote design exception. It is a
scope boundary on apply ordering, exactly matching the environment-agnostic
memory's own statement that "the first channel we deploy to is a local
channel ... real Vultr API ... scoped to remote channels." Every deferral
has a named successor INIT: INIT-102 Flux, INIT-103 Infisical, INIT-106
Crossplane, INIT-113 workloads, INIT-118 HA. This satisfies the
no-deferred-stubs requirement that postponed work has a named follow-up.

The findings below are implementation-tightening notes for the cloud-init
template, the `vultr-vms` module variable contract, and slice-header
semantics. None compromises the substrate contract or the local
done-state proof.

## Findings table

| ID | Type | Severity | Finding | Proposal cite | Recommendation |
|----|------|----------|---------|---------------|----------------|
| S1 | hack | MEDIUM | Cloud-init `runcmd` block as shown has no strict-mode guarantee. If `curl -sfL https://get.k3s.io \| sh -` fails, the subsequent `cp` and `chmod` still execute and cloud-init reports success — silent exit-0 on a broken install. Section 2.7 hedges with "may add strict shell flags." Falls under the brief's "Failure modes that exit 0 silently" shortcut category. | §2.7 lines 305-323 | Replace "may" with "must": require the rendered `user_data` to either install with `set -euo pipefail` semantics or chain `curl … && cp && chmod` so a failed installer aborts cleanly. Make this part of SLICE-101.03 acceptance, not deferred to remote-apply work. |
| S2 | hardcoded | MEDIUM | k3s install URL `https://get.k3s.io` is piped into `sh` without integrity verification of the installer script. The k3s **binary** checksum is verified by the installer internally, and `INSTALL_K3S_VERSION` pins the version, but the installer payload itself is not pinned. The brief lists this exact pattern as a shortcut. | §2.7 line 317 | Either (a) document the upstream-pattern rationale and binary-level integrity in §4 as an accepted tradeoff, or (b) download the installer to a temp file, verify a known SHA256, then exec. The proposal currently does neither and the shortcut category is explicitly named in the brief. |
| S3 | fake-completion | LOW | Every slice in §3 uses the header "Local-verification acceptance commands." The brief's shortcut list calls out "Proposal language that quietly uses 'verification' framing instead of 'deployment' framing" as a misinterpretation of local-as-first-deployment. The slice contents do require real cluster bring-up (esp. SLICE-101.02, 101.05), so the substance is correct — but the label drifts. | §3 all six slice headers (lines 506, 539, 576, 619, 656, 694) | Rename to "Local deployment acceptance commands" (or "Local channel deployment + verification") so the framing matches the environment-agnostic memory's "local IS a deployment target" principle. Pure documentation fix. |
| S4 | coupling | LOW | The cloud-init template assumes a Linux base image with cloud-init enabled, but `os_id` (or `os_slug`) is not in the `platform-cluster-vms` variable contract. If a future channel selects a non-cloud-init image, the bootstrap silently no-ops at apply time. Hidden coupling between the channel schema and the OS catalog. | §2.6 lines 286-299; §2.7 entire | Add a required `os_id` variable to the `platform-cluster-vms` module with a default named Ubuntu LTS that has cloud-init pre-installed, and surface it in the channel schema. Address in SLICE-101.03. |
| S5 | deferred | LOW | "Post-INIT-117 remote deployment work" names a phase boundary, not a specific successor INIT, for "first real remote k3s apply and remote kubeconfig retrieval." Every other deferral points to a concrete INIT (102/103/106/113/118). Per the brief: "unnamed is a shortcut." Borderline — phase boundaries are weaker than ticket IDs. | §1 lines 75-77; §7 lines 877-878 | Either coin a specific INIT (e.g., INIT-119 First Remote Control Cluster Apply) and use it consistently, or list the constituent post-INIT-117 successors explicitly in §7 and §1. Address in SLICE-101.06 docs. |
| S6 | deferred | LOW | The channel schema (§2.3) and Tradeoff #9 reference a `bootstrap.token` field for `vultr-vms` channels, but the `platform-cluster-vms` variable contract (§2.6) lists no token variable, and the cloud-init template (§2.7) has no token slot. For single-server INIT-101 topology k3s auto-generates a token, so functionally nothing breaks; for HA (INIT-118) it becomes load-bearing. The schema/module/template asymmetry could mislead the implementer. | §2.3 line 197; §2.7 line 323; §4 #9 lines 742-744 | Either fully omit the token from §2.3 and Tradeoff #9 (with a comment that INIT-118 will add it) or define the field shape now: a `sensitive = true` string variable on the module, a `${k3s_token}` placeholder in the template, and a schema entry naming INIT-118 as the consumer. Either choice is fine — the inconsistency is the shortcut. |
| S7 | hack | LOW | Section 2.6 module variable contracts do not call out `sensitive = true` for any field. The Vultr `user_data` attribute can appear in `tofu plan` output, and SLICE-101.03 explicitly runs `tofu -chdir=infra/roots/channels/dev plan -out=...`. If S6's token field or a future credential is added without `sensitive = true`, it leaks into plan diffs and CI logs. The brief lists "Secret material in user_data without sensitive marking" and "kubeconfig retrieval that exposes credentials in CI logs" as shortcut categories. | §2.6 lines 286-299; §2.12 lines 467-469; SLICE-101.03 line 587 | Add to SLICE-101.03 acceptance: variables that flow into `user_data` are marked `sensitive`, and the rendered cloud-init `user_data` does not echo bootstrap material in `tofu plan` output. |

## Convergence statement

INIT-101 is ready to proceed to hookpoint research. The proposal honors the
environment-agnostic principle (same distribution, single template, real
local deployment, no kind/minikube fallback), the no-backwards-compatibility
convention (no VKE module, schema, alias, archive, banner, or dual reader),
and the no-deferred-stubs convention (every postponed item names a
successor INIT, the harness fails closed on missing local cluster, the
remote-plan skip is gated only on missing credentials and never substitutes
for the local k3d proof).

The seven findings are implementation-time tightenings: cloud-init
robustness and integrity (S1, S2), slice-header semantics (S3), OS pinning
on the remote module (S4), one specificity gap on the post-INIT-117
successor reference (S5), and the schema/module/template token-shape
asymmetry plus its sensitive-marking implication (S6, S7). Two findings
(S1, S2) should be folded into SLICE-101.03 acceptance before
implementation begins; the other five can be tightened during hookpoint
research or implementation review without re-running the risk gate. None
invalidates the substrate contract, the slice decomposition, or the
done-state proof.
