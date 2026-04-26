# INIT-104 Shortcut Risk

## Verdict

LOW

## Summary

Shortcut risk is LOW. The proposal does not defer, stub, or weaken any of the
examined INIT-104 shortcut surfaces without naming an owner. The local path has a
real Infisical-to-Kubernetes Secret proof, real MinIO deployment, stable bucket
Job lifecycle under Flux, live S3 PUT/GET byte comparison, Pod-restart durability
assertion, second bring-up idempotency assertion, and pinned `mc` tooling.

The only residual observation is wording consistency in the Vultr handoff:
Section 8 still lists dashboard creation as one possible operator-supplied path,
while the D-record binds Vultr bucket ownership to INIT-106 with operator/CLI
fallback as break-glass only. That is not a gate because INIT-106 is named, but
implementation docs should preserve the D-record wording so dashboard creation
does not become the primary operational path.

## Findings

| ID | Surface | Severity | Shortcut assessment | Proposal cites | Required change |
|---|---|---:|---|---|---|
| SC-001 | Secret bootstrap sequencing | LOW | No shortcut found. Kustomize order is explicitly not treated as readiness. The proposal uses `InfisicalSecret` readiness, Secret refs, MinIO readiness probes, and bucket Job `mc ready` rather than sleeps or a hand-waved dependency. `bring-up-local-channel.sh` runs storage bootstrap after INIT-103 identity bootstrap and before Flux waits on object-storage reconciliation. | `.pipeline/proposal.md:88-89`, `.pipeline/proposal.md:121-125`, `.pipeline/proposal.md:341-351`, `.pipeline/proposal.md:464-487`, `.pipeline/proposal.md:579-601`, `.pipeline/proposal.md:831-845` | None. Keep the condition waits and `mc ready` in implementation. |
| SC-002 | One-shot Job lifecycle under Flux | LOW | No shortcut found. The proposal chooses a stable one-shot Job with no TTL; Flux re-apply leaves it Complete, and intentional recreation requires deleting `Job/create-sample-bucket`. `mc mb --ignore-existing` makes a recreated Job safe against an existing bucket. | `.pipeline/proposal.md:490-499`, `.pipeline/proposal.md:793-797`, `.pipeline/proposal.md:856-858`, `.pipeline/proposal.md:983-984` | None. |
| SC-003 | Local durability for single-node MinIO | LOW | No shortcut found for INIT-104's local bar. The proposal binds a `local-path` PVC and requires the harness to upload a retained object, delete the MinIO Pod, wait for a new Ready Pod, confirm the PVC remains Bound, list the bucket, and GET/byte-compare the retained object. k3d cluster recreate durability is not promised; backup, restore, PVC snapshots, object replication, retention, and disaster recovery are named for INIT-112. | `.pipeline/proposal.md:300-310`, `.pipeline/proposal.md:319-386`, `.pipeline/proposal.md:850-855`, `.pipeline/proposal.md:882-887`, `.pipeline/proposal.md:904-905`, `.pipeline/proposal.md:924-925` | None. Docs should preserve the data-loss warning for PVC or cluster teardown. |
| SC-004 | Live S3 harness assertion | LOW | No shortcut found. The harness is not just a bucket-exists check: `sample-s3-roundtrip.py` reads the five `S3_*` vars, PUTs bytes, GETs bytes, compares content, deletes the object, and fails on mismatch. | `.pipeline/proposal.md:638-649`, `.pipeline/proposal.md:807-809`, `.pipeline/proposal.md:848-849`, `.pipeline/proposal.md:990-991` | None. |
| SC-005 | Vultr OS bucket creation | LOW | No blocking shortcut found. INIT-104 does not provision remote storage, but the proposal names the successor owner: INIT-106 owns Vultr Object Storage subscription and bucket provisioning through the Crossplane Vultr provider `Bucket` claim, with operator/CLI fallback as break-glass only. Section 8's broader "dashboard, `vultr-cli`, Vultr API, or future Terraform/OpenTofu" wording should not override that binding. | `.pipeline/proposal.md:668-693`, `.pipeline/proposal.md:912-913`, `.pipeline/proposal.md:947-948`, `.pipeline/proposal.md:994-996` | None for the gate. Keep dashboard creation documented only as manual/break-glass, not the primary reproducible path. |
| SC-006 | Storage credential rotation | LOW | No shortcut found. Rotation is explicitly deferred to INIT-115; INIT-104 only seeds initial local proof credentials and does not rotate MinIO root, Vultr OS, or app-scoped credentials. | `.pipeline/proposal.md:603-608`, `.pipeline/proposal.md:768-769`, `.pipeline/proposal.md:929-931` | None. |
| SC-007 | MinIO root Secret round-trip proof | LOW | No shortcut found. The local harness must read the Infisical source values without printing them, decode the synced Kubernetes Secret, and assert byte equality for both MinIO root keys. | `.pipeline/proposal.md:840-844`, `.pipeline/proposal.md:997-999` | None. |
| SC-008 | `mc` CLI bootstrapping | LOW | No shortcut found. The MinIO server image, `mc` image, and host `mc` binary are pinned to explicit release tags; the host binary has a checksum and the installer acceptance criteria verify it. The prose says the selected release was the latest verified during proposal verification, but the executable contract is an exact tag plus checksum, not `latest`. | `.pipeline/proposal.md:271-282`, `.pipeline/proposal.md:742-752`, `.pipeline/proposal.md:1005-1006` | None. |
| SC-009 | Channel template extension and re-bring-up idempotency | LOW | No shortcut found. The schema is strict, child inheritance is specified, aliases are rejected, storage bootstrap leaves existing credentials unchanged, and the harness requires a second bring-up plus Flux reconcile and a second S3 round trip. | `.pipeline/proposal.md:242-260`, `.pipeline/proposal.md:592-593`, `.pipeline/proposal.md:733-739`, `.pipeline/proposal.md:856-858` | None. |
| SC-010 | Anti-scope completeness | LOW | No shortcut found. Access policy, credential rotation, fine-grained bucket policies, bucket lifecycle policies, server-side bucket encryption, bucket versioning, and object lifecycle TTL are explicitly deferred to INIT-115; backup/restore/PVC snapshots/object replication/retention are explicitly deferred to INIT-112. | `.pipeline/proposal.md:907-931`, `.pipeline/proposal.md:950-951`, `.pipeline/proposal.md:1003-1004` | None. |

## Convergence

INIT-104 converges to LOW shortcut risk.

No proposal change is required for this gate. The implementation handoff should
carry forward three non-gating details:

1. The bucket Job remains a stable no-TTL one-shot Job; rerun after manual bucket
   deletion requires deleting `Job/create-sample-bucket`.
2. Local durability means PVC-backed survival across MinIO Pod restart, not k3d
   cluster delete/recreate or backup durability.
3. Vultr bucket creation's primary reproducible owner is INIT-106; any dashboard
   path is manual/break-glass only.
