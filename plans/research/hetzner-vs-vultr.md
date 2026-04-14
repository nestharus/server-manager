# Hetzner vs Vultr for Kubernetes Hosting

As of 2026-04-14.

## 1. Executive summary

For a self-hosted, enterprise-leaning platform that wants the robust version rather than the cheapest workable version, Vultr is the stronger Kubernetes hosting choice.

The decisive reason is simple: Vultr has a first-party managed Kubernetes product (`VKE`) with managed control plane, managed load balancers, broader networking options, broader regional reach, direct-connect-style private connectivity, and a cleaner path for GitOps-heavy day-2 operations. Hetzner has strong cloud primitives, excellent price discipline, and a healthy Kubernetes ecosystem around its cloud-controller-manager and CSI driver, but from the official product/docs set reviewed here it still reads as an infrastructure provider for self-managed Kubernetes rather than a managed Kubernetes platform. That last point is an evidence-based inference from the official catalog/docs, not a quoted vendor statement.

That difference matters for the intended stack. Services like Authentik, Pomerium, Smallstep, Flux, Buildkite workers, and a growing set of internal platform services benefit more from lower control-plane burden, stronger private-networking options, and broader managed service coverage than from the absolute lowest VM price.

The main caution on Vultr is networking maturity around VKE: Vultr’s December 2025 docs still say VKE uses legacy VPC networking and is not compatible with `VPC 2.0`, while also carrying wording about `VPC 2.0` end-of-life on December 31, 2025. That is not a deal-breaker, but it is a real diligence item before committing.

## 2. Capability comparison table

| Area | Hetzner | Vultr | Better fit for this platform |
| --- | --- | --- | --- |
| Managed Kubernetes maturity | No first-party managed Kubernetes service surfaced in the official cloud/docs set I reviewed. Kubernetes on Hetzner is a self-managed pattern using official `hcloud-cloud-controller-manager` and `csi-driver`. | First-party managed Kubernetes (`VKE`), free control plane, managed control-plane upgrades, official docs for GitOps, observability, storage, scaling, and cluster operations. | Vultr |
| Control-plane constraints | You own control plane HA, upgrades, etcd, node lifecycle, ingress, and cluster recovery. | Vultr upgrades the control plane automatically; worker nodes are still your responsibility. No built-in ingress controller. | Vultr |
| Private networking / VPC-like model | Private L3 networks, IPv4-only, zone-scoped, not automatically encrypted. Routing exists, but firewalls do not protect private-network traffic. | VPC-backed clusters, attach existing VPCs in-region, same-region private networking, Direct Connect available, richer enterprise network surface. | Vultr |
| Load balancing / ingress | Managed LB is solid, supports public/private targets and managed certificates, but firewalls cannot be applied to load balancers yet. | Managed L4/L7 LB with TLS termination and VPC integration. VKE requires you to choose and deploy your own ingress controller. | Vultr |
| Firewalls | Stateful, inbound and outbound allow rules, but cannot secure private networks or load balancers. | Platform firewall surface is broad, but instance firewall only filters incoming traffic; egress filtering stays host-level. | Slight edge Vultr overall, but with caveats |
| Block storage / persistence | Volumes are triplicated and can scale to 10 TB, but Hetzner does not provide backups or snapshots for volumes. Server backups/snapshots exclude volumes. | Block storage, same-location attach requirement, block storage snapshots supported. Automatic instance backups still do not cover attached block storage. | Vultr |
| Object storage / data locality | S3-compatible object storage, but currently only in `fsn1`, `nbg1`, and `hel1`. Strong EU locality; weak global footprint. | S3-compatible object storage with archival tiering and materially broader regional coverage than Hetzner. | Vultr |
| GPU / compute shapes | Cloud footprint across EU, US, Singapore; GPU story is primarily dedicated GPU servers, not a managed-K8s-native GPU platform. | Broad cloud GPU catalog, official VKE/GPU positioning, 32 global cloud regions. VKE supports mixed node pools, but not bare-metal workers. | Vultr |
| Regional footprint | Good but still modest: EU plus Ashburn, Hillsboro, Singapore. | Much broader global footprint and more obvious enterprise/hybrid posture. | Vultr |
| Pricing model | Extremely attractive infra pricing with hourly billing and monthly caps, but you pay with ops burden. | VKE control plane is free; you pay for nodes, load balancers, storage, and surrounding services. Higher spend, lower ops burden. | Vultr for robust platform; Hetzner for cost-driven self-management |
| Terraform / OpenTofu ergonomics | Very mature `hcloud` provider for primitives; Kubernetes lifecycle is pushed into your own modules and cluster stack. | Mature `vultr` provider with native Kubernetes resource surface plus networking/storage resources; better single-provider automation story. | Vultr |

## 3. Networking and storage analysis

### Networking

Hetzner networking is competent but not especially enterprise-shaped. Its Cloud Networks provide private layer-3 connectivity, can span locations only within the same network zone, support only IPv4, and are not automatically encrypted. Routes exist, but only cloud servers can act as route gateways. Firewalls are stateful and can control both inbound and outbound allow rules, but they still do not secure private-network traffic and still cannot be attached to Hetzner Cloud load balancers. For a platform with identity, edge-access, and internal service-mesh-style traffic, that is a meaningful limitation.

Hetzner does have a useful bridge to dedicated hardware through `vSwitch`, but only in the `eu-central` network zone and with a limit of one vSwitch per Network. That is handy for hybrid cloud-plus-dedicated layouts, but it is not the same thing as a richer VPC platform.

Vultr’s networking surface is stronger for this use case. VKE clusters live inside a VPC, can reuse an existing VPC in the same region, and integrate with Vultr load balancers, block storage, and private connectivity. Vultr also has Direct Connect for private links into enterprise or multicloud environments. That matters if the platform later needs private CI runners, private package mirrors, cross-cloud failover, or a more formal network boundary around auth and control-plane services.

The major Vultr caveat is doc ambiguity around VKE networking. Vultr’s VKE docs updated on December 18, 2025 still say VKE is compatible with legacy VPC only and not with `VPC 2.0`, while Vultr’s networking docs simultaneously describe `VPC 2.0` as its private isolated network product and a support article notes an end-of-life date of December 31, 2025 for `VPC 2.0`. My read is that Vultr’s networking terminology changed faster than its VKE docs. That is survivable, but I would verify the exact post-2025 VKE/VPC behavior with Vultr before committing.

### Storage

Hetzner’s block storage is technically strong at the volume level. Volumes are network-attached block devices, triplicated across three physical servers, billed hourly with a monthly cap, and scalable from 10 GB to 10 TB. The problem is operational completeness: Hetzner explicitly does not provide snapshots or backups for volumes, and server backups/snapshots exclude attached volumes. For stateful platform services, that means you must build a real volume-level backup strategy yourself from day one.

Hetzner object storage is S3-compatible and attractive for EU data residency, but today it is only available in Falkenstein, Nuremberg, and Helsinki. That is fine for EU-centric backups, artifacts, and logs; it is weaker for a broader multi-region platform.

Vultr’s storage surface is more rounded. Block Storage is a first-class service with snapshots, though volumes must stay in the same location as the attached instance. Vultr also states that automatic server backups do not cover attached block storage, so stateful services still need deliberate snapshot/backup workflows. Object Storage is S3-compatible, has archival storage and lifecycle policies, and has broader geographic reach than Hetzner. For a broader platform with artifacts, backups, logs, OCI layers, and possibly Buildkite caches, Vultr is the better default.

Bottom line on data: neither provider makes stateful platform operations trivial, but Vultr gives you fewer missing pieces.

## 4. OpenTofu/provider maturity

Hetzner’s `hcloud` provider is mature and heavily used: Terraform Registry currently shows it as a partner provider, version `1.60.1`, with `13.4M` installs. That is strong evidence that the provider itself is not the weak point. The issue is scope. Hetzner automation is excellent for servers, networks, load balancers, volumes, firewalls, and related primitives, but Kubernetes day-2 work still lives in your cluster stack. In practice, that means Talos/k3s/kubeadm modules, your own upgrade playbooks, your own disaster recovery, and your own node/control-plane choreography.

Vultr’s provider is also mature enough to take seriously: Terraform Registry currently shows version `2.30.1` and `5.4M` installs, with resources and data sources spanning Kubernetes, VPC, `vpc2`, load balancers, block storage, object storage, reserved IPs, and the rest of the platform surface. For OpenTofu/Terraform users, that is a materially better day-2 story for a broader platform because more of the platform can stay inside one provider graph.

The caveat is that Vultr’s provider surface reflects the same network-model transition visible in the docs: both `vultr_vpc` and `vultr_vpc2` appear in the registry. I would treat that as a migration hazard, not a blocker. By contrast, Hetzner’s automation is conceptually cleaner, but only because the Kubernetes complexity is pushed out of the provider and back onto you.

My inference on OpenTofu specifically: both providers appear operationally compatible with standard Terraform/OpenTofu workflows, but Vultr is the easier substrate if the goal is a managed-Kubernetes-centered platform, while Hetzner is the easier substrate only if you intentionally want to own the cluster lifecycle.

## 5. Risks and caveats

- Vultr’s VKE networking documentation is internally awkward post-2025. Resolve the `legacy VPC` vs `VPC 2.0` wording before locking in architecture.
- Vultr still leaves meaningful Kubernetes operations to you: worker-node upgrades are manual, ingress is not bundled, and instance firewalls are inbound-only.
- VKE does not support bare-metal worker nodes. If you want a unified managed K8s cluster that also uses dedicated bare metal, Vultr is not that.
- Hetzner’s biggest risk is not one missing feature but the overall operational shape: no first-party managed Kubernetes, no volume snapshots/backups, no firewall protection for private networks, no firewall attachment on load balancers, and private network traffic is not automatically encrypted.
- Hetzner object storage is currently EU-only. That is good for EU locality, bad for broader platform placement flexibility.
- On both providers, stateful services still need explicit backup and restore design. Do not confuse VM backup features with a real storage or database recovery plan.

## 6. Recommendation for this platform

Choose Vultr as the primary Kubernetes hosting provider for this platform.

That recommendation is not about price; it is about operational shape. The planned stack wants a managed control plane, better private-networking options, a broader managed service envelope, better global placement options, and fewer self-inflicted operational responsibilities around auth, ingress, storage plumbing, and cluster lifecycle. Vultr is materially closer to that target.

Choose Hetzner only if the team is intentionally choosing self-managed Kubernetes as part of the platform design and is comfortable owning control-plane lifecycle, backup gaps around volumes, and a thinner network-security envelope. Hetzner is strong infrastructure, but for this specific brief it is the better raw substrate, not the better platform host.

Before purchase, I would do one concrete diligence step with Vultr: confirm in writing, as of 2026-04-14, how new VKE clusters map onto Vultr’s current VPC model and which Terraform resources are the supported long-term path for that network attachment model.

## Primary sources

- Hetzner load balancer overview: https://docs.hetzner.com/networking/load-balancers/overview/
- Hetzner firewall FAQ: https://docs.hetzner.com/cloud/firewalls/faq/
- Hetzner networks FAQ: https://docs.hetzner.com/networking/networks/faq/
- Hetzner volumes overview: https://docs.hetzner.com/cloud/volumes/overview/
- Hetzner backups/snapshots overview: https://docs.hetzner.com/cloud/servers/backups-snapshots/overview/
- Hetzner object storage overview: https://docs.hetzner.com/storage/object-storage/overview/
- Hetzner cloud pricing / locations / volumes: https://www.hetzner.com/cloud/volumes/
- Vultr Kubernetes docs: https://docs.vultr.com/products/kubernetes
- Vultr VKE support index: https://docs.vultr.com/support/products/vke
- Vultr VKE upgrades: https://docs.vultr.com/support/products/vke/how-does-vultr-kubernetes-engine-cluster-handle-upgrades
- Vultr VKE GitOps support: https://docs.vultr.com/support/products/vke/how-does-vultr-kubernetes-engine-support-gitops-workflows
- Vultr VKE and VPC compatibility: https://docs.vultr.com/support/products/vke/can-i-connect-my-vke-cluster-to-a-vpc2-network
- Vultr attach existing VPC to VKE: https://docs.vultr.com/support/products/vke/can-i-attach-an-existing-vpc-to-a-new-vke-cluster
- Vultr VPC 2.0 docs: https://docs.vultr.com/products/network/vpc-2
- Vultr firewall docs: https://docs.vultr.com/products/network/firewall
- Vultr load balancer docs: https://docs.vultr.com/products/load-balancer
- Vultr block storage docs: https://docs.vultr.com/products/cloud-storage/block-storage
- Vultr object storage docs: https://docs.vultr.com/products/cloud-storage/object-storage
- Vultr Direct Connect: https://www.vultr.com/products/direct-connect/
- Terraform Registry `hcloud` provider: https://registry.terraform.io/providers/hetznercloud/hcloud/latest
- Terraform Registry `vultr` provider: https://registry.terraform.io/providers/vultr/vultr/latest
