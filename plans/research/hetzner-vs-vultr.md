# Hetzner Cloud vs Vultr for Production Kubernetes Hosting

_Research date: April 11, 2026_

This compares Hetzner Cloud and Vultr for a production Kubernetes platform hosting Kong, Authentik, Pomerium, Flux, Prometheus/Grafana, PostgreSQL, and multiple application services. This is not a recommendation memo. It is a current-state comparison of product shape, pricing, limits, and operational implications.

One important framing point: these providers are not directly symmetric. Vultr has a first-party managed Kubernetes product, Vultr Kubernetes Engine (VKE). Hetzner Cloud, as of this research date, does not appear to have a first-party managed Kubernetes control plane product. Hetzner’s official material instead focuses on cloud primitives, Kubernetes integrations, and community tutorials for running Kubernetes on top of Hetzner infrastructure. That difference affects almost every category below.

## Comparison Table

| Area | Hetzner Cloud | Vultr |
|---|---|---|
| Managed K8s | No first-party managed control plane found in current product catalog; official positioning is self-managed K8s on Hetzner Cloud plus integrations/tutorials | VKE is a fully managed control plane with no additional control-plane fee |
| K8s control plane cost | N/A as a first-party managed service | Free; you pay for worker nodes, load balancers, and storage |
| K8s worker minimums | Self-managed, so your minimum is whatever cluster design you choose within account limits | At least 1 node pool, at least 1 worker node, minimum 2 GB RAM per worker |
| K8s version policy | No managed service version matrix because no first-party managed control plane found | Public docs describe supported-version selection and managed control-plane upgrades, but the docs I found do not publish a fixed public version matrix |
| $5/$10/$20-ish compute | CPX11: 2 vCPU / 2 GB / 40 GB for €5.99; CPX21: 3 vCPU / 4 GB / 80 GB for €9.99; CPX31: 4 vCPU / 8 GB / 160 GB for €17.99 | 1 vCPU / 1 GB / 25 GB / 0.5 TB for $5; 1 vCPU / 2 GB / 55 GB / 2 TB for $10; 2 vCPU / 4 GB / 80 GB / 3 TB for $20 |
| Higher-performance compute | Dedicated-vCPU CCX13 starts at 2 vCPU / 8 GB / 80 GB for €16.49 | Separate high-frequency and optimized compute families; VKE worker docs say 2 GB RAM and up |
| Account limits | Current official FAQ does not publish a universal 5-server default; limits are account-specific, visible in the console “Limits” tab, and increases are manual via “Request change” | No single public default cap found; docs repeatedly describe account-specific limits/quotas and support-ticket increases |
| Object storage | S3-compatible; base price €7.72/mo includes 1 TB storage and 1 TB egress; extra storage €0.0104/TB-hour, extra egress €1.19/TB | S3-compatible; Standard starts at $18/mo for 1 TB storage + 1 TB egress; extra storage $18/TB-month, extra egress $10/TB |
| Managed PostgreSQL | No first-party managed PostgreSQL service found in current cloud catalog | Yes; PostgreSQL 14 through current stable, automated backups, PITR by plan, replicas, failover |
| Networking | Private networks, stateful firewalls, load balancers, floating IPs, volumes; strong fit for self-managed clusters | VPC, firewalls, managed load balancers, reserved IPs, block storage, Direct Connect, managed LB integration with VKE |
| Terraform/OpenTofu | Official `hcloud` provider is mature for core infra, but because Hetzner lacks first-party managed K8s/DBaaS there is no native managed-K8s/managed-Postgres coverage | Official `vultr` provider covers `vultr_kubernetes`, `vultr_database`, `vultr_object_storage`, `vultr_load_balancer`, `vultr_vpc`, `vultr_vpc2`, and more |
| API rate limits | 3600 requests/hour per project | 30 requests/second per source IP |
| US + EU regions | EU-central: FSN/NBG/HEL; US-east: ASH; US-west: HIL; also SIN | 32 regions globally, with broad US and EU coverage including Atlanta, Chicago, Dallas, Los Angeles, Miami, New Jersey, Seattle, Amsterdam, Frankfurt, London, Madrid, Paris, Stockholm, Warsaw |
| Reliability/support signals | 99.9% cloud SLA, 24/7 email support, official status page shows recent cloud and object-storage incidents plus regional capacity limits | Managed service positioning, 24/7/365 support messaging, official status page per-region dashboards, trust-center/security posture, broad managed-service surface |

## 1. Managed Kubernetes

### Hetzner

I did **not** find a first-party Hetzner-managed Kubernetes control plane in the current product catalog. That is an inference from what Hetzner does publish:

- The cloud product pages describe Kubernetes as a workload you run on cloud servers.
- Hetzner highlights official Kubernetes integrations, including cloud API integrations and Kubernetes support in its automation story.
- Hetzner’s community/tutorial content includes “Deploy production-ready Kubernetes on Hetzner with Edka,” which reads as a partner or community deployment path rather than a native managed-Kubernetes product.

For production planning, that means “Hetzner K8s” today should be treated as **self-managed Kubernetes on Hetzner infrastructure**, not as an EKS/GKE/VKE equivalent. You can absolutely build a production cluster there, but the burden for control-plane lifecycle, etcd design, upgrades, and many day-2 operations stays with you or with third-party tooling.

### Vultr

Vultr **does** have a first-party managed offering: VKE. The control plane is free, and Vultr charges only for provisioned worker nodes, load balancers, and storage. Public support docs say a VKE cluster requires at least one node pool with at least one worker node, and each worker must have at least 2 GB RAM. VKE handles control-plane upgrades automatically; worker-node upgrades remain a customer action. VKE also supports GitOps workflows with Flux or Argo CD, integrates with Vultr load balancers and block storage, uses Calico as the default CNI, and supports node-pool autoscaling.

One caveat: Vultr’s public support docs are stronger on operational behavior than on publishing a static version matrix. I found support docs for “supported Kubernetes version must be selected during cluster creation” and upgrade handling, but not a clean public page listing every currently selectable minor release.

## 2. Compute Pricing

For the small-to-medium “platform component” band, Hetzner is very aggressive on raw CPU/RAM/storage value. The closest direct comparison bands are:

### Hetzner regular-performance shared instances

- CPX11: 2 vCPU, 2 GB RAM, 40 GB SSD, €5.99/mo
- CPX21: 3 vCPU, 4 GB RAM, 80 GB SSD, €9.99/mo
- CPX31: 4 vCPU, 8 GB RAM, 160 GB SSD, €17.99/mo

### Vultr regular cloud compute

- $5: 1 vCPU, 1 GB RAM, 25 GB SSD, 0.5 TB bandwidth
- $10: 1 vCPU, 2 GB RAM, 55 GB SSD, 2 TB bandwidth
- $20: 2 vCPU, 4 GB RAM, 80 GB SSD, 3 TB bandwidth

For equivalent monthly spend, Hetzner generally exposes more vCPU/RAM/storage. Vultr tends to expose the cleaner managed-services envelope around that compute, especially once you want managed Kubernetes and managed databases. So the decision is not just “which VM is cheaper”; it is “how much infrastructure do you want to self-assemble around the VMs.”

Hetzner also offers dedicated-vCPU general-purpose instances, starting with CCX13 at 2 vCPU, 8 GB RAM, 80 GB SSD for €16.49/mo. That is relevant if you want to isolate ingress, auth, or database-adjacent workloads from noisy-neighbor risk without moving to a separate bare-metal tier.

## 3. Account Limits

### Hetzner

The “default 5-server limit” is widely discussed in community threads, but the **current official Hetzner FAQ does not publish that fixed number**. What the official docs do say, as of April 11, 2026, is:

- accounts have a default limit of 20 projects;
- each account also has resource limits visible in the console’s **Limits** tab;
- increases are manual via **Request change** and reviewed case-by-case during business hours.

Operationally, that means Hetzner still has a quota-gated onboarding model. You should expect limit management to matter if you want a serious production Kubernetes footprint with multiple node pools, staging, jump hosts, ingress nodes, and database replicas.

### Vultr

I did not find a single public “default server cap” equivalent to the Hetzner anecdotes. Vultr’s docs instead repeatedly describe **account-specific limits**, quotas, and support-assisted increases. That usually implies fewer public onboarding surprises, but also less predictability from docs alone because the exact ceiling depends on account profile, product, and region.

## 4. Object Storage

### Hetzner Object Storage

Hetzner’s object storage is S3-compatible. The clearest official pricing data on the live page is:

- Base price: **€7.72/mo**
- Base hourly: **€0.0124**
- Included: **1 TB storage** and **1 TB egress**
- Extra storage: **€0.0104 per TB-hour**
- Extra egress: **€1.19 per TB**

Hetzner also states that ingress, internal traffic inside the `eu-central` network zone, and S3 API calls are free. The service supports up to 100 buckets, 100 TB each.

### Vultr Object Storage

Vultr’s object storage is also S3-compatible. Standard tier pricing is:

- Standard: **$18/mo**
- Included: **1 TB storage** and **1 TB egress**
- Extra storage: **$18/TB-month**
- Extra egress: **$10/TB**

Vultr also has Premium, Performance, and Accelerated storage tiers, which may matter for image registries, large Prometheus remote-write archives, or artifact-heavy CI/CD. Hetzner’s pricing is materially lower on pure cost per TB and egress.

## 5. Managed PostgreSQL

### Hetzner

I did not find a first-party managed PostgreSQL service in Hetzner’s current cloud catalog. That means PostgreSQL on Hetzner is, for now, either:

- self-hosted on cloud servers;
- built on third-party SaaS elsewhere; or
- run via a third-party control plane/tooling layer.

For a production Kubernetes platform, that increases architectural responsibility substantially if you want HA Postgres, PITR, cross-region replicas, backups, and clean failover without introducing another vendor.

### Vultr

Vultr has a real managed-database product. PostgreSQL support starts at **PostgreSQL 14** and goes to the most recent stable release. Managed-database docs also describe:

- automated backups;
- point-in-time recovery by plan;
- user-initiated restore/fork actions;
- read-only replica nodes;
- automated failover in multi-node clusters;
- up to **3** read-only replicas per cluster;
- the ability to place replica nodes in different Vultr locations from the primary.

Pricing is not cheap in the same way Hetzner compute is cheap. The pricing page surfaced PostgreSQL configurations such as 4 GB / 1 vCPU / 30 GB at **$90/mo** and 8 GB / 2 vCPU / 50 GB at **$180/mo**, with HA/replica variants higher. But Vultr is offering a genuine managed operational surface, not just a VM with PostgreSQL installed.

## 6. Networking

### Hetzner

Hetzner has the primitives you need for a serious self-managed platform:

- private Networks;
- stateful Firewalls;
- Floating IPs;
- Load Balancers;
- Volumes;
- official API/CLI support.

This makes Hetzner structurally viable for Kubernetes, but you assemble more of the platform yourself. Load balancer pricing is modest on an hourly basis, starting around **€0.0120/hr** for LB11. Hetzner’s load-balancer tiers scale targets and certificates rather than pushing you toward a heavy base charge.

### Vultr

Vultr’s networking story is broader and more “platform-shaped”:

- VPC / VPC 2.0 resources in the Terraform provider;
- managed Load Balancers starting at **$10/mo**;
- Firewalls;
- Reserved IPs at **$3/mo**;
- Block Storage and File System options;
- Direct Connect;
- VKE integration with Vultr load balancers, block storage, and private networking.

One nuance: the current VKE docs say VKE is on the legacy VPC model and is **not compatible with VPC 2.0**. That matters if you want to standardize on the newest Vultr network model for everything. Also, Vultr load balancers are bandwidth-neutral, so egress is still counted on backend instances instead of the load balancer itself.

## 7. Terraform / OpenTofu Maturity

### Hetzner

Hetzner’s official Terraform provider, `hetznercloud/hcloud`, looks mature for core infrastructure. Official release notes show ongoing releases and recent work on DNS GA and network attachment resources. Official Hetzner materials also point to automation support for Terraform, Ansible, Kubernetes, Python, and Go. For a self-managed Kubernetes platform, that is enough to provision servers, private networks, firewalls, load balancers, IPs, and volumes reliably.

The limitation is product-surface, not provider quality: because Hetzner does not currently expose first-party managed Kubernetes or managed PostgreSQL, the provider cannot give you native resources for those services.

### Vultr

Vultr’s official `vultr/vultr` provider has broader first-party resource coverage for a platform stack. Vultr’s own Terraform docs list resources including:

- `vultr_kubernetes`
- `vultr_kubernetes_node_pools`
- `vultr_database`
- `vultr_object_storage`
- `vultr_load_balancer`
- `vultr_vpc`
- `vultr_vpc2`
- `vultr_container_registry`

That is a stronger fit if you want OpenTofu/Terraform to manage more of the control plane using first-party abstractions instead of only raw VMs and networking. Since OpenTofu consumes standard Terraform providers, this strongly suggests practical OpenTofu compatibility as well, though that is an inference from provider format rather than a separate OpenTofu certification statement.

## 8. API Quality

Hetzner’s API surface is concise and developer-oriented. Official docs state a default rate limit of **3600 requests/hour per project**, with standard limit headers. Hetzner also officially maintains Go and Python SDKs.

Vultr’s API is broader because its product surface is broader. Official docs say all customer-portal functions are accessible by API, the API is OpenAPI-described, and the rate limit is **30 requests/second per IP**. Vultr docs also expose CLI, Terraform reference, and SDK/client guidance for multiple languages.

In practical terms:

- Hetzner’s API is smaller but straightforward for infra primitives.
- Vultr’s API is more platform-complete and better aligned with managed-service automation.

## 9. Regions, Reliability, and Community Surface

Hetzner’s official cloud footprint is much narrower but now clearly spans both Europe and the US: FSN, NBG, HEL, ASH, HIL, plus SIN. Vultr’s public region list is much broader, with 32 cloud data center regions and deep US/EU density.

Reliability signals also differ:

- Hetzner publishes a **99.9%** cloud SLA and a transparent incident/status site. The status site shows both routine maintenance and recent cloud/API/object-storage incidents, plus regional capacity constraints.
- Vultr’s public posture emphasizes broad managed infrastructure, a status dashboard with per-region notifications, and trust-center/security messaging. Vultr also markets **24/7/365** support and a larger managed-services envelope.

On community/developer surface:

- Hetzner has an active official docs site, community tutorials, official SDKs, and an “awesome-hcloud” ecosystem list. The community around self-managed Kubernetes on Hetzner is real, but it is community-heavy precisely because Hetzner does not give you a first-party managed K8s product.
- Vultr has broader official docs across managed services, Terraform, API, and support articles. The ecosystem is less “DIY cluster module”-centric because more of the stack is exposed as native services.

## Bottom-Line Shape of the Tradeoff

If you strip this down to platform shape rather than branding:

- **Hetzner** is a low-cost, high-value infrastructure substrate for teams willing to self-manage Kubernetes and likely self-manage PostgreSQL or outsource it elsewhere.
- **Vultr** is a more complete managed platform surface, especially once managed Kubernetes, managed PostgreSQL, and Terraform-managed first-party resources matter more than absolute VM price-performance.

That is the core distinction to preserve when you evaluate these providers for an enterprise Kubernetes stack. This is not just “cheap VPS vs slightly pricier VPS.” It is “DIY cloud substrate” versus “mid-market managed cloud platform.”

## Sources

- Hetzner Cloud main product page: <https://www.hetzner.com/cloud>
- Hetzner regular-performance pricing page: <https://www.hetzner.com/cloud/regular-performance>
- Hetzner general-purpose pricing page: <https://www.hetzner.com/cloud/general-purpose>
- Hetzner load balancer page: <https://www.hetzner.com/cloud/load-balancer/>
- Hetzner object storage page: <https://www.hetzner.com/storage/object-storage>
- Hetzner Cloud FAQ: <https://docs.hetzner.com/cloud/general/faq/>
- Hetzner Cloud API reference: <https://docs.hetzner.cloud/reference/cloud>
- Hetzner cloud SLA: <https://docs.hetzner.com/general/company-and-policy/slas-cloud/>
- Hetzner status: <https://status.hetzner.com/>
- Hetzner Terraform provider releases: <https://github.com/hetznercloud/terraform-provider-hcloud/releases>
- Hetzner official ecosystem list: <https://github.com/hetznercloud/awesome-hcloud>
- Vultr pricing: <https://www.vultr.com/pricing/>
- Vultr Kubernetes pricing/support doc: <https://docs.vultr.com/support/products/vke/how-much-does-the-vultr-kubernetes-engine-cost>
- Vultr support/products PDF collection: <https://docs.vultr.com/public/doc-assets/pdfs/collection_item/support-products.pdf>
- Vultr Terraform docs: <https://docs.vultr.com/reference/terraform>
- Vultr API overview: <https://www.vultr.com/api/>
- Vultr API support docs: <https://docs.vultr.com/support/platform/api>
- Vultr main site and locations: <https://www.vultr.com/>
- Vultr datacenter locations page: <https://www.vultr.com/features/datacenter-locations/>
- Vultr object storage product page: <https://www.vultr.com/products/object-storage/>
- Vultr load balancer pricing doc: <https://docs.vultr.com/support/platform/billing/how-are-vultr-load-balancers-priced>
- Vultr load balancer bandwidth doc: <https://docs.vultr.com/support/products/load-balancer/how-is-bandwidth-charged-for-vultr-load-balancers>
- Vultr support portal and support messaging: <https://www.vultr.com/support/>
- Vultr control panel/support messaging: <https://www.vultr.com/features/control-panel/>
- Vultr status page: <https://status.vultr.com/>
- Vultr trust center: <https://www.vultr.com/trust-center>
