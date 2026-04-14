# Platform decisions overlay

Corrections and updates to `unified-platform-index.md` based on user
decisions and research results that landed after the merge.

## Auth stack — LOCKED (user confirmed)

| Component | Decision | Notes |
| --- | --- | --- |
| Human identity | `Authentik` | Confirmed by the user after the merge launched |
| Authorization engine | `OPAL/Cedar` | Confirmed by the user; close the earlier open question in the merged index |
| Access proxy | `Pomerium` | Confirmed by the user |
| `Smallstep` | Conditional | Keep only if a broader internal PKI/CA is needed; do not require it just for SSH |

## Research corrections landed after the merge

| Topic | Updated reading | Implication |
| --- | --- | --- |
| `Buildkite` | Replaces most of the Dagger/custom CI orchestration layer | Treat `Buildkite` as canonical CI/CD direction |
| `Flux CD` | Replaces `Argo CD` in the GitOps layer | Keep `Flux` as the reconciler direction |
| `Kafka` / `Debezium` / `Redis` pipeline | Not required on the minimum path | Defer the heavy event pipeline until later phases |
| Self-hosted S3 alternatives | Provider-native object storage is preferred first | Keep `SeaweedFS` as the self-hosted fallback |
| `Pomerium` + `Smallstep` | `Pomerium` covers SSH access in 2026 | `Smallstep` is only justified if the platform needs a fuller PKI substrate |

## Still open after this overlay

- Hosting decision: `Hetzner` vs `Vultr`
- `Logto RLS pagination` research still running
- `OpenTofu providers` research still running
