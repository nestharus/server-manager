# Self-hosted S3-compatible storage for Kubernetes (2026)

Date: 2026-04-14

## 1. Executive summary

For this platform, there are really two sane directions.

First, the lowest-risk path for a small team is to keep Kubernetes self-hosted but keep object storage managed and S3-compatible. Among the evaluated providers, Vultr is the better primary application bucket: broader feature coverage, versioning, multiple locations, and straightforward pricing. Hetzner is materially cheaper, but its object storage is explicitly a single-data-center-per-bucket service with only basic S3 compatibility and no replication API support, so it fits better as a secondary backup/archive target than as the only primary object layer.

Second, if object storage must be self-hosted inside Kubernetes, MinIO is still the strongest S3-compatible option technically, but its 2026 packaging changes matter: `AIStor Free` is single-node, while horizontally scalable multi-node deployment is now `Enterprise Lite` or `Enterprise`. SeaweedFS is the best open-source compromise for a small team, but its own documentation still frames MinIO as the stricter S3 implementation. Garage is elegant and operationally light, but too incomplete to recommend as a general S3 replacement for a platform default. Ceph/Rook is the most storage-platform-grade option, but the operational tax is only justified if the platform also wants Ceph for block/file storage or already has people who can run Ceph well.

Recommended platform direction: default to managed S3-compatible storage as the primary object layer. If policy requires self-hosted object storage inside Kubernetes, use MinIO plus offsite replication/backup to a provider bucket. Avoid Ceph unless the broader platform genuinely needs Ceph-class storage.

## 2. Option comparison table

Ops burden and GitOps fit are partly inferred from the documented deployment models, not directly vendor-scored.

| Option | S3 API fit | Durability / replication posture | K8s / GitOps fit | Day-2 burden | Cost shape | Bottom line |
|---|---|---|---|---|---|---|
| MinIO AIStor | Excellent | Erasure coding within erasure sets; site, bucket, and batch replication; peer-site healing; offsite sync via `mc mirror` | Strong: first-party operator, Helm charts, CRDs, `AdminJob`, spread-zone support | Medium | Hardware plus software subscription for multi-node | Best self-hosted choice if paying for multi-node is acceptable |
| Garage | Partial | Configurable replication factor, geo-distribution, automatic scrub, metadata resync, metadata snapshots; no S3 replication endpoints | Decent: Helm chart, Kubernetes discovery; still requires manual layout steps | Low to medium | Low software cost, modest hardware | Elegant but not a full S3 replacement |
| SeaweedFS | Good enough, not strict | Rack/DC-aware replication, master failover, active-active async cross-cluster replication, warm-data erasure coding, cloud backup/tiering | Strong: operator, Helm, explicit FluxCD guidance | Medium | Low software cost, moderate hardware and ops | Best OSS compromise if exact S3 semantics are not mandatory |
| Ceph/Rook RGW | Very good, broad feature set | Erasure-coded data pools, replicated metadata, multisite active-active, S3 replication API, strong failure-domain control | Strongest K8s integration: Rook CRDs, OBC, COSI | High | Highest hardware and operator cost | Only justified if the platform also wants a broader storage platform |
| Vultr Object Storage | Good managed subset | Versioning yes; replication no; multi-location strategy is backup/sync, not native replication | Very easy: external bucket, secret management, lifecycle policies | Low | Predictable monthly tiers from $18/TB-month equivalent entry point plus egress | Best managed app-facing bucket among evaluated providers |
| Hetzner Object Storage | Basic managed subset | Single selected DC per bucket; erasure coding within cluster; replication no | Very easy | Low | Very cheap base plan; no per-request fees; EU-only locations | Good low-cost backup/archive target, weaker primary app bucket |

## 3. Operational analysis

### MinIO

MinIO remains the cleanest "looks like S3" self-hosted answer. The Kubernetes story is mature: first-party operator, Helm charts, production CRDs, and Kubernetes-native admin jobs. Replication and recovery tooling are good enough to build a serious DR plan around.

The main change is strategic, not technical. In 2026, MinIO's official packaging makes the free tier single-node. If this platform wants multi-node MinIO in Kubernetes, that is now a paid decision. For a small team, that may still be cheaper than staffing Ceph, but it is no longer the old "free multi-node drop-in S3" assumption.

### Garage

Garage has the best simplicity story of the self-hosted OSS options. It is self-contained, geo-distribution-aware, dynamically tolerant of changing node addresses, and light enough to run in less traditional environments. That matters if the platform wants a small-footprint distributed object store without bolting on a full storage stack.

The problem is feature surface. Missing versioning, ACLs, bucket policies, object lock, tagging, notification APIs, replication APIs, and server-side encryption keep it from being a safe default "S3 replacement" for a general platform in 2026.

### SeaweedFS

SeaweedFS is the most plausible open-source middle ground. It has real Kubernetes support, explicit FluxCD instructions in the operator repo, replication across clusters, cloud backup/tiering, and a practical architecture for blob-heavy workloads.

The tradeoff is that it is not the cleanest S3 emulation target. Even SeaweedFS' own README contrasts it with MinIO and says MinIO is the better choice for strict S3 behavior. Also, SeaweedFS usually means more moving parts than MinIO or Garage: master, volume servers, filer, embedded IAM, and often an external filer metadata store.

### Ceph / Rook

Rook makes Ceph feel Kubernetes-native, but it does not make Ceph simple. If you run it well, it offers the strongest failure-domain control and the deepest storage feature set in this list. It is the right answer when object storage is only one part of a larger storage program.

It is the wrong answer for a small team that only needs a reliable S3-like bucket service for one platform. You inherit OSD health management, pool design, recovery tuning, capacity planning, upgrade choreography, and a larger blast radius when storage goes bad.

### Vultr and Hetzner

Both managed providers radically reduce day-2 burden. The GitOps shape is simple: credentials, bucket policies, lifecycle, and external secret management.

The tradeoff is obvious: you stop operating storage and start depending on provider implementation details and product scope. That is acceptable if the goal is provider-neutral S3 API consumption rather than literal in-cluster self-hosting.

## 4. Durability and failure-mode notes

### MinIO

MinIO's durability model is erasure-set based. With a 16-drive set at default `EC:4`, reads and writes continue with 12 healthy drives; at `EC:8`, writes require `K+1` to prevent split-brain. If write quorum is lost but read quorum remains, the cluster serves reads and rejects writes until enough drives return. Site replication continuously syncs peer clusters and can resynchronize damaged data from a healthy site, but asynchronous replication means a `PUT` can succeed before the remote copy exists.

### Garage

Garage is replica/quorum based rather than "AWS-like bucket feature complete". With `replication_factor = 3`, it is designed around multi-copy resilience and geo-distributed placement. Scrub runs automatically every 25 to 35 days, metadata tables resync hourly, and metadata snapshots exist specifically to recover metadata corruption.

Important caveat: Garage recommends LMDB for distributed clusters, but its docs explicitly warn that LMDB is prone to corruption after an unclean shutdown. The recovery story is snapshots and metadata reconstruction from peer nodes, not magic.

### SeaweedFS

SeaweedFS can do rack/DC-aware replication, automatic master failover, active-active async cross-cluster replication, and optional erasure coding for warm data. That gives it a credible durability story, but the exact failure behavior depends heavily on how replication, filer metadata, and tiering are configured.

That means robustness is real, but more design-dependent than with a managed provider bucket. This is an inference from SeaweedFS' documented architecture and deployment model.

### Ceph / Rook

Ceph is strongest when failure domains are intentionally separated and pools are designed correctly. Rook's object-store examples explicitly assume at least three OSDs on different nodes and recommend stronger erasure-code layouts such as `4+2` or `8+4` for production. For DR, Ceph supports active-active multisite and an S3 replication API.

The key caveat is that Ceph itself warns that running a single Ceph cluster across WAN links is not recommended unless latency is very low. Real DR means separate clusters and deliberate multisite design.

### Vultr

Vultr exposes a useful managed S3 subset with versioning, lifecycle, multipart upload, presigned URLs, policies, and tagging, but no bucket replication. Its own docs point users toward backing up to another location or using multiple locations and syncing between them. In other words: good managed durability inside a location, but geo redundancy is still an explicit user concern.

### Hetzner

Hetzner states that each bucket is stored in the chosen location and within a single data center, with erasure-coded chunks spread across multiple servers. It says the system can maintain integrity even if up to three storage servers fail. It also explicitly says object storage is only one part of a secure backup strategy.

That makes Hetzner a good economical copy, not the entire resilience plan.

## 5. Risks and caveats

- Old assumptions about MinIO being the obvious free multi-node S3 replacement are stale in 2026.
- Garage is too incomplete for ecosystems that rely on versioning, bucket policies, ACLs, object lock, notification APIs, or native replication APIs.
- SeaweedFS should be tested against the exact SDKs, backup tools, and application behaviors this platform will use; its own docs concede MinIO is stricter for S3 compatibility.
- Ceph/Rook only pays off when the organization can absorb its storage-operations burden.
- Managed providers remove ops burden but reintroduce provider dependency and provider-specific feature ceilings.
- None of these options removes the need for offsite backup, restore testing, and DR drills.

## 6. Recommendation for this platform

Primary recommendation: use managed S3-compatible object storage as the platform default, not in-cluster self-hosted object storage. Among the evaluated providers, Vultr is the stronger primary bucket for application data, while Hetzner is the better low-cost secondary target for backups and archival copies.

If the platform must self-host the object layer inside Kubernetes, use MinIO AIStor with a paid multi-node tier and replicate off-cluster to a provider bucket. That is the best balance of S3 compatibility, Kubernetes ergonomics, and practical recoverability for a small team.

Do not use Garage as the default platform object layer in 2026. Do not use Ceph/Rook unless the platform also wants Ceph for block/file storage or can justify a real storage-operations function. Use SeaweedFS only if MinIO's commercial model is unacceptable and the team is willing to validate S3 compatibility against its exact workload.

## Sources

- MinIO pricing and packaging: <https://www.min.io/pricing>
- MinIO erasure coding: <https://docs.min.io/enterprise/aistor-object-store/operations/core-concepts/erasure-coding/>
- MinIO replication: <https://docs.min.io/enterprise/aistor-object-store/administration/replication/>
- MinIO site replication: <https://docs.min.io/enterprise/aistor-object-store/administration/replication/site-replication/>
- MinIO Kubernetes operator reference: <https://docs.min.io/enterprise/aistor-object-store/reference/kubernetes/>
- Garage features: <https://garagehq.deuxfleurs.fr/documentation/reference-manual/features/>
- Garage S3 compatibility matrix: <https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/>
- Garage configuration and replication behavior: <https://garagehq.deuxfleurs.fr/documentation/reference-manual/configuration/>
- Garage durability and repairs: <https://garagehq.deuxfleurs.fr/documentation/operations/durability-repairs/>
- Garage Kubernetes deployment: <https://garagehq.deuxfleurs.fr/documentation/cookbook/kubernetes/>
- SeaweedFS upstream repository and feature list: <https://github.com/seaweedfs/seaweedfs>
- SeaweedFS operator: <https://github.com/seaweedfs/seaweedfs-operator>
- Ceph Object Gateway overview: <https://docs.ceph.com/en/latest/radosgw/>
- Ceph multisite sync policy and S3 replication API: <https://docs.ceph.com/en/latest/radosgw/multisite-sync-policy/>
- Ceph multisite guidance: <https://docs.ceph.com/en/nautilus/radosgw/multisite/>
- Ceph erasure coding: <https://docs.ceph.com/en/latest/rados/operations/erasure-code/>
- Rook object storage overview: <https://rook.io/docs/rook/latest/Storage-Configuration/Object-Storage-RGW/object-storage/>
- Hetzner object storage overview: <https://docs.hetzner.com/storage/object-storage/overview/>
- Hetzner general FAQ: <https://docs.hetzner.com/storage/object-storage/faq/general/>
- Hetzner supported actions: <https://docs.hetzner.com/storage/object-storage/supported-actions/>
- Hetzner pricing page / product page: <https://www.hetzner.com/storage/object-storage/>
- Vultr S3 compatibility matrix: <https://docs.vultr.com/products/cloud-storage/object-storage/s3-compatibility-matrix>
- Vultr object storage FAQ: <https://docs.vultr.com/products/cloud-storage/object-storage/faq>
- Vultr limits and performance tiers: <https://docs.vultr.com/products/cloud-storage/object-storage/limits>
- Vultr billing: <https://docs.vultr.com/support/platform/billing/how-is-object-storage-billed>
