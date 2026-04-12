# Self-Hosted S3-Compatible Storage for K8s (2026)

## Scope and framing

Goal: evaluate object storage options that can serve S3-compatible workloads for applications running on or alongside Kubernetes, with likely hosting on Vultr or Hetzner. This includes both self-hosted systems and provider-native hosted object storage.

Important note on the `%` values below: vendors rarely publish a literal "S3 compatibility percentage". The percentages in this document are **estimates**, inferred from official compatibility matrices where available, documented feature coverage, and obvious missing features. They should be read as decision support, not as a formal benchmark.

## Executive summary

For a **small K8s cluster**, provider-native object storage is usually the right default. It removes the hardest part of the problem: operating a durable storage system. If the cluster lives on **Vultr**, Vultr Object Storage is the most operationally straightforward option. If the cluster lives on **Hetzner**, Hetzner Object Storage is the cheapest hosted option, but its S3 feature coverage is materially narrower and it is clearly positioned more for backups, archives, and moderate application workloads than for hot-path, high-request object storage.

If you must self-host inside or beside K8s, the most practical 2026 options are:

- **SeaweedFS** for the best balance of license, K8s support, and operator burden.
- **Garage** if low footprint and geo-distributed replicas matter more than broad S3 parity.
- **MinIO** if maximum S3 fidelity and performance matter most, but only if the AGPL and the 2025+ community-distribution changes are acceptable.

**Ceph RGW** remains strong technically, but for a small cluster it is usually the wrong answer unless you already want Ceph for block and file storage too.

## Comparison table

| Option | S3 compatibility (estimated) | K8s packaging | Small-scale footprint | License | Replication / backup story | Small-scale cost (100GB-1TB) | Bottom line |
|---|---:|---|---|---|---|---|---|
| MinIO | 95-100% | First-party operator, Helm/Kustomize | Moderate to high for a resilient setup; quickstart uses 4 nodes | AGPLv3 | Strong bucket and site replication | Software free, infra cost only | Best S3 behavior, but licensing and community-distribution changes are real 2026 concerns |
| Garage | 60-75% | No first-party operator/Helm surfaced in upstream docs/repo | Low | AGPLv3 | Native geo-distributed replication is a core strength | Software free, infra cost only | Excellent lightweight/edge option, but less K8s-polished and lower S3 fidelity |
| SeaweedFS | 75-85% | First-party operator, Helm, CSI | Low to moderate | Apache-2.0 | Cross-cluster replication, cloud tiering, async backup patterns | Software free, infra cost only | Strong pragmatic self-hosted default |
| Ceph RGW | 85-95% | Rook operator | High | LGPLv2.1/Ceph stack licenses | Mature multisite + Ceph durability | Software free, infra cost only | Enterprise-capable, but heavy for small clusters |
| Vultr Object Storage | 80-90% | No operator needed; external endpoint/secret | Zero in-cluster | Proprietary managed service | No native bucket replication in matrix; use app/tooling | $18/TB/mo standard, 1TB included | Best low-friction choice if already on Vultr |
| Hetzner Object Storage | 65-80% | No operator needed; external endpoint/secret | Zero in-cluster | Proprietary managed service | No native replication; use app/tooling | €4.99/$5.99 base incl. 1TB | Cheapest hosted option, but feature set is narrower |
| Cloudflare R2 | 80-90% | No operator needed; external endpoint/secret | Zero in-cluster | Proprietary managed service | Provider-managed durability; migration tools, but not self-run multisite | ~$1.50 for 100GB, ~$15 for 1TB + request costs | Very attractive when egress cost matters or assets are internet-facing |

## Detailed findings

## 1. MinIO

MinIO remains the reference point for high-performance S3-compatible software. Upstream still describes it as a Kubernetes-native high-performance object store with an S3-compatible API, and the official operator remains a first-party deployment model for Kubernetes. The operator docs still center on a **4-node tenant** pattern, which is a signal about how MinIO thinks resilient production deployments should look.

The big 2026 issue is not core technology. It is **operational and licensing posture**:

- The open-source code is **AGPLv3**.
- The official repo now states the community edition is **source-only distributed**.
- The same repo says the project is in **maintenance mode** and directs users toward AIStor tiers for fuller packaging/support.

That combination matters for platform teams. AGPL is not automatically disqualifying for internal use, but it is a real legal review item if you modify and redistribute, embed, or commercialize around it. The shift away from maintained community binaries/images also increases supply-chain and operations friction versus 2024-era expectations.

Kubernetes support is still mature. The operator requires Kubernetes 1.30+, supports custom storage classes, and manages tenant CRDs. The official docs note one PVC per volume plus two extra PVCs for metrics/logs. For a typical 4-node, 4-drive tenant that means **16 data PVCs plus 2 extra**.

Resource footprint: there is no simple official "minimum for small prod" number. The upstream quickstart assumes a 4-node tenant, and MinIO's own performance guidance targets much larger hardware. For a real resilient deployment, treat MinIO as **moderate-to-high footprint**, not lightweight. It can run smaller for dev/test, but that is not the same thing as durable production.

Replication is strong:

- Per-bucket replication.
- Two-way bucket replication.
- Multi-site replication.

Operationally, MinIO is excellent if you specifically need strong S3 semantics and high throughput on your own infrastructure. For a small K8s cluster, though, the tradeoff is no longer just "infra complexity vs performance". In 2026 it is also **"AGPL + source-only community path + maintenance-mode OSS repo"**.

Verdict: technically strong, but no longer the easiest recommendation for a small general-purpose platform.

## 2. Garage

Garage is explicitly aimed at **small-to-medium-scale self-hosted** deployments and emphasizes **geo-distributed replication**, resilience when some nodes are unreachable, and a lightweight operating model. Upstream says Deuxfleurs has used it in production since its first release in **2020**, which is meaningful evidence of maturity even though it is much smaller than MinIO or Ceph.

Its core differentiator is topology: Garage is designed for clusters spanning different physical locations. If your K8s plan includes nodes in more than one site or you want a cheap multi-location object layer without standing up Ceph multisite, Garage is unusually well aligned to that problem.

The tradeoffs are:

- **AGPLv3**, same general licensing caution as MinIO.
- No first-party operator/Helm packaging surfaced in the current upstream repo/docs I reviewed.
- Smaller ecosystem and less obvious enterprise-style support path.

Resource footprint is the main attraction. Upstream repeatedly positions Garage as lightweight and easy to operate. It does not publish a hard minimum in the materials I found, so the safest statement is: **no official minimum published**. Practically, Garage is the one option in this list that plausibly fits well on small nodes and edge-style clusters. For planning, assume a small multi-node deployment can start far below Ceph and somewhat below MinIO.

S3 compatibility is lower than MinIO. Garage calls itself S3-compatible, but it is not marketed as broad parity with every AWS corner case. That is why the estimate here is only **60-75%**. It is a fit when your applications mostly need the common object CRUD, multipart, presigned-URL, and bucket-policy style surface, not the full long-tail of S3 behavior.

Verdict: best fit when low footprint and multi-site resilience matter more than broad S3 parity or polished K8s tooling.

## 3. SeaweedFS

SeaweedFS is the most balanced self-hosted option in this set. Upstream presents it as a fast distributed storage system that supports blobs, objects, files, and data-lake patterns. The project explicitly lists:

- S3 API
- active-active replication
- Kubernetes CSI
- SeaweedFS Operator
- erasure coding
- cloud tiering / backup patterns

This is a strong combination for platform work. It also uses the **Apache 2.0** license, which is much easier for most teams than AGPL.

Architecturally, SeaweedFS is not "just an S3 server". It has master, volume, filer, and optionally IAM pieces. That is more moving parts than Garage, but less platform gravity than Ceph. The operator is a meaningful advantage for K8s deployment.

Resource footprint is favorable. Upstream shows a single-binary `weed mini` path and a `weed server -s3` path for simple environments, which is a good sign that dev/test and small production setups are feasible without huge machinery. For production on Kubernetes, the footprint is still **multi-service**, so call it low-to-moderate rather than ultra-light.

S3 compatibility looks solid for common workloads but not as strong as MinIO. SeaweedFS advertises S3 support, but it does not publish the kind of comprehensive compatibility posture MinIO does, and there are recurring upstream issue threads around multipart/object-lock/copy edge cases. That is why the estimate lands at **75-85%** rather than 90%+.

Replication and backup are good:

- Filer store replication for metadata HA.
- Active-active cross-cluster replication.
- Async replication to cloud providers.
- Gateway patterns to remote object stores.

Verdict: for a small-to-medium K8s platform that wants self-hosted object storage without Ceph weight or AGPL pressure, **SeaweedFS is the most practical default**.

## 4. Ceph RADOS Gateway

Ceph RGW is the heavyweight option. Technically, it is strong. Ceph documents a large subset of the S3 API as supported and even publishes a feature-status table. Rook provides the standard Kubernetes operator path, and multisite replication is a mature concept.

But the question is not whether Ceph can do object storage. It can. The question is whether it is realistic for a **small K8s cluster**.

For most small clusters, the honest answer is: **only if storage itself is a primary platform competency**.

Reasons:

- Rook/Ceph production guidance expects **three or more nodes** for a resilient platform.
- Ceph hardware guidance says **4GB+ RAM per OSD daemon** and **2GB+ per monitor**.
- Fast media is strongly recommended for monitor/manager metadata and RGW index pools.
- Ceph brings significant operational surface area even before adding RGW, object users, realms, zones, and multisite.

If you already want Ceph for block + file + object, then RGW is reasonable. If you only want S3-compatible buckets for app assets and backups, it is usually overkill.

S3 compatibility is good, likely **85-95%**, but not perfect. For example, Ceph's docs explicitly mark bucket replication as **partial** and limited across zones. Still, it is much closer to full parity than Garage or Hetzner Object Storage.

Verdict: excellent enterprise storage stack, poor default for a small cluster that only needs S3.

## 5. Vultr Object Storage

If the workloads run on Vultr, this is the easiest answer operationally. Vultr exposes an S3-compatible service with regional endpoints and zero in-cluster storage burden. The current docs are stronger than generic marketing pages because they include a concrete **S3 compatibility matrix** and limits page.

Important compatibility details from Vultr's docs:

- Supported: ACLs, lifecycle, versioning, CORS, multipart, tags, policies, presigned URLs.
- Not supported: access logging, inventory, notifications, bucket replication, website hosting.

That makes Vultr materially more transparent than many vendors. It is S3-compatible, but not full-parity. Estimated compatibility: **80-90%**.

Pricing at small scale:

- Standard: **$18/month** includes 1TB storage + 1TB outbound.
- Premium: $36/month.
- Performance: $50/month.
- Accelerated: $100/month.

For **100GB**, you still pay the base tier price. For **1TB**, the standard tier lines up cleanly. For small app platforms, this is expensive versus R2 or Hetzner on raw $/GB, but much cheaper than self-hosting once operator time is included.

Verdict: strong default if you are already on Vultr and do not need unsupported S3 features like replication or notifications.

## 6. Hetzner Object Storage

Hetzner's object storage is cheap and simple, but its documentation is unusually candid about where it fits and where it does not.

Strengths:

- Very low base cost.
- S3-compatible interface.
- Up to 100 buckets, 100TB each.
- Erasure-coded backend.
- Explicitly suitable for backups, archives, static content, software distribution, and disaster recovery.

Limits:

- Docs call it **basic compatibility** with the standard S3 actions/data types.
- Notable missing features include **request payment, notifications, accelerate, website, analytics, inventory, logging, metrics, ownership controls, replication, tagging, restore, select, torrent, GetObjectAttributes**.
- Hetzner explicitly says the service is **not ideal for high-frequency small-file workloads, latency-sensitive apps, or direct serving to thousands of HTTP clients**.

That is a very different posture from MinIO. Hetzner Object Storage is best understood as a cost-efficient hosted object layer, not as a near-drop-in full-S3 replacement for every workload.

Pricing at small scale is excellent:

- **€4.99 / $5.99 per month** includes 1TB storage and 1TB egress.
- Overage from the press material is **€0.0067 / $0.0080 per TB-hour** for storage and **€1.00 / $1.20 per TB** egress.

Verdict: best cheap hosted bucket for backups, artifacts, and moderate application storage on Hetzner. Less compelling for hot-path application storage with broad S3 assumptions.

## 7. Cloudflare R2

R2 is not self-hosted and not provider-native to Vultr/Hetzner, but it is highly relevant because it removes egress charges and works cleanly from K8s via the S3 API.

Its strongest advantages are:

- **No egress fees** for direct R2 egress.
- Very low storage price.
- Explicit S3-compatibility documentation with implemented/unimplemented API features.
- Works well with public internet distribution patterns.

Pricing is straightforward:

- Standard storage: **$0.015/GB-month**.
- Infrequent access: **$0.01/GB-month**.
- No egress fees.
- Request pricing still applies.

So rough storage-only cost is:

- **100GB**: about **$1.50/month**
- **1TB**: about **$15/month**

That is usually cheaper than Vultr Standard and often competitive with Hetzner once outbound traffic is considered.

Compatibility is strong but not full. Cloudflare publishes exact implemented and unimplemented operations, which is better than hand-wavy "S3-compatible" claims. The result is an estimated **80-90%** compatibility band.

Verdict: excellent option when workloads read objects over the public internet, CDN-style delivery matters, or outbound transfer would otherwise dominate cost.

## Recommendation for this platform

If the platform just needs reliable S3-compatible buckets for app assets, backups, artifacts, or user uploads, **do not self-host object storage inside a small K8s cluster unless there is a strong product reason**.

Recommended order:

1. **Vultr Object Storage** if running on Vultr and unsupported features are acceptable.
2. **Cloudflare R2** if internet egress and public distribution costs matter.
3. **Hetzner Object Storage** if on Hetzner and the workload is backup/static/warm-storage shaped.
4. **SeaweedFS** if self-hosting is mandatory.
5. **Garage** if geo-distribution and tiny footprint matter more than S3 breadth.
6. **MinIO** only if you explicitly accept AGPL and the new community-ops posture.
7. **Ceph RGW** only if you already want Ceph as a broader storage platform.

## Sources

- MinIO OSS repo: https://github.com/minio/minio
- MinIO operator: https://operator.min.io/
- MinIO site/bucket replication docs: https://min.io/docs/minio/linux/administration/bucket-replication/enable-server-side-multi-site-bucket-replication.html
- Garage upstream repo mirror: https://github.com/deuxfleurs-org/garage
- SeaweedFS repo: https://github.com/seaweedfs/seaweedfs
- SeaweedFS operator: https://github.com/seaweedfs/seaweedfs-operator
- Ceph RGW S3 API docs: https://docs.ceph.com/en/quincy/radosgw/s3/
- Ceph hardware recommendations: https://docs.ceph.com/en/reef/start/hardware-recommendations/
- Rook object storage docs: https://rook.io/docs/rook/latest-release/Storage-Configuration/Object-Storage-RGW/object-storage/
- Vultr object storage product/pricing: https://www.vultr.com/products/object-storage/
- Vultr S3 compatibility matrix: https://docs.vultr.com/products/cloud-storage/object-storage/s3-compatibility-matrix
- Vultr limits/performance: https://docs.vultr.com/products/cloud-storage/object-storage/limits
- Hetzner object storage overview: https://www.hetzner.com/storage/object-storage/overview/
- Hetzner supported actions: https://docs.hetzner.com/storage/object-storage/supported-actions/
- Hetzner FAQ/general workload fit: https://docs.hetzner.com/storage/object-storage/faq/general/
- Hetzner launch pricing: https://www.hetzner.com/pressroom/object-storage/
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare R2 S3 compatibility: https://developers.cloudflare.com/r2/api/s3/api/
