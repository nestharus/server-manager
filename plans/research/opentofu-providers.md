# OpenTofu Provider Maturity: Vultr vs Hetzner

Date: 2026-04-11

## Bottom line

If the platform wants managed Kubernetes, managed databases, and a mostly single-provider IaC story, Vultr is materially ahead. The official `vultr/vultr` provider covers the expected platform building blocks: VKE, managed databases, object storage, DNS, firewalls, load balancers, VPC, and newer networking primitives like NAT gateways. The official `hetznercloud/hcloud` provider is mature in a different sense: it is well-maintained, explicitly OpenTofu-aware, and strong for compute, networking, load balancers, DNS, storage volumes, certificates, and backup/storage-box workflows. But Hetzner simply does not offer the managed control-plane services the platform would otherwise want, so the IaC surface shifts from “compose managed products” to “build and operate more yourself.”

The implication is straightforward. Vultr is the stronger fit if the target architecture wants provider-managed K8s and managed Postgres. Hetzner is viable if the team is willing to run Kubernetes and databases on self-managed servers, or if the platform is intentionally minimizing provider lock-in by treating the cloud provider mostly as a source of VMs, networks, volumes, and load balancers.

## 1. Vultr provider: what it can manage

The official Vultr provider repository shows a broad resource inventory in `website/docs/r`, which is the best primary-source summary of supported resources because it is the maintained docs tree for the provider itself: <https://github.com/vultr/terraform-provider-vultr/tree/master/website/docs/r>.

From that resource list, the important platform-level capabilities are:

- `kubernetes` and `kubernetes_node_pools`: managed VKE clusters and node pools are first-class resources.
- `database`, `database_replica`, `database_user`, `database_db`, `database_connection_pool`, `database_connector`, `database_quota`, `database_topic`: managed database support is substantial, not just a single “database instance” resource.
- `object_storage` and `object_storage_bucket`: managed object storage is covered at both service and bucket level. Vultr’s official docs describe this as “managed S3-compatible object storage” and expose a dedicated Terraform resource reference: <https://docs.vultr.com/reference/terraform/resources/object_storage>.
- `dns_domain` and `dns_record`: DNS zones and records are supported.
- `firewall_group` and `firewall_rule`: firewall policy is supported.
- `load_balancer`: load balancers are supported.
- `vpc` and `vpc2`: private networking is supported, including the newer VPC model.
- `nat_gateway`, `nat_gateway_firewall_rule`, `nat_gateway_port_forwarding_rule`: newer network egress/NAT constructs are supported.
- `instance`, `bare_metal_server`, `block_storage`, `reserved_ip`, `snapshot`, `startup_script`, `ssh_key`: the usual IaaS primitives are also covered.

That means the Vultr provider can express a credible “all major infra in one graph” topology: cluster, database, object storage, DNS, firewalls, load balancer, and network fabric in one provider.

### What seems missing or weaker on Vultr

The gaps are not in the core categories the user asked about; those are present. The missing pieces are more about edge services and completeness around the broader Vultr catalog.

Based on the provider docs tree, obvious absences include:

- No first-class CDN resource in the provider docs tree.
- No obvious managed secrets, message queue, or serverless functions surface in the provider docs tree.
- Some product areas appear as service-level resources but not necessarily with complete sub-resource coverage. Example: object storage is present, but the provider docs tree does not suggest deep S3-policy-style management comparable to AWS.

The practical reading is that Vultr’s provider is strong where the platform likely cares most: deployable application infrastructure. It is less obviously a “manage every console feature” provider.

## 2. Hetzner `hcloud`: what it can manage

The official Hetzner provider docs tree is here: <https://github.com/hetznercloud/terraform-provider-hcloud/tree/main/docs/resources>. The repository README explicitly states the provider supports “Terraform or OpenTofu” and should work with tools that implement Terraform plugin protocol v6: <https://github.com/hetznercloud/terraform-provider-hcloud>.

The `docs/resources` directory shows the following important platform capabilities:

- `server`, `server_network`, `placement_group`, `primary_ip`, `floating_ip`, `rdns`, `ssh_key`, `snapshot`: core compute lifecycle is well-covered.
- `network`, `network_subnet`, `network_route`: private networking is supported.
- `load_balancer`, `load_balancer_network`, `load_balancer_service`, `load_balancer_target`: load balancers are supported, including the surrounding attachments and services.
- `firewall`, `firewall_attachment`: firewalls are supported.
- `zone`, `zone_record`, `zone_rrset`: DNS is now supported directly in `hcloud`.
- `certificate`, `managed_certificate`, `uploaded_certificate`: TLS certificate management is supported.
- `volume`, `volume_attachment`: block storage is supported.
- `storage_box`, `storage_box_snapshot`, `storage_box_subaccount`: Hetzner’s Storage Box product is supported.

This is a strong provider for “traditional cloud primitives.” You can build VM-based systems, private networking, ingress/load balancing, DNS, firewalling, backups, snapshots, and storage workflows directly in OpenTofu.

### What `hcloud` cannot manage, because Hetzner does not offer it

The platform-level absences are structural, not just provider omissions:

- No managed Kubernetes service.
- No managed Postgres or general managed relational database service.

So there is no Hetzner equivalent to Vultr VKE or Vultr managed databases for the provider to expose.

### What appears to exist outside `hcloud` or outside the current provider scope

Two distinctions matter:

1. Hetzner Object Storage exists as a product and is S3-compatible. Hetzner’s docs say Object Storage is managed through the Hetzner S3 API for bucket/object operations, with S3 credentials created in the Hetzner Console: <https://docs.hetzner.com/storage/object-storage/faq/general> and <https://docs.hetzner.com/storage/object-storage/faq/buckets-objects>. Hetzner’s “What’s New” page says the product became generally available on 2024-12-03: <https://docs.hetzner.cloud/whats-new>.
2. But Object Storage does not appear in the `hcloud` provider resource list. By contrast, Storage Box does. So Object Storage is usable as an S3 backend target, but not currently something you should expect `hcloud` itself to provision.

That distinction matters operationally. On Hetzner, remote state in provider-native object storage is possible, but the bucket bootstrap may be partly out-of-band or managed through a different S3-compatible provider rather than through `hcloud`.

## 3. Provider maturity

### Vultr

Primary sources:

- Repo: <https://github.com/vultr/terraform-provider-vultr>
- Releases: <https://github.com/vultr/terraform-provider-vultr/releases>

Observed signals as of 2026-04-11:

- Latest release: `v2.30.1`, dated 2026-03-04.
- Recent prior releases: `v2.30.0` on 2026-02-26, `v2.29.1` on 2026-02-10, `v2.29.0` on 2026-02-09, `v2.28.1` on 2026-01-30, `v2.28.0` on 2025-12-18.
- Open issues visible on the repo page: 59.
- Stars/forks visible on the repo page: 217 stars, 72 forks.
- Total commits visible on the repo page: 1,061.

Interpretation:

- Release cadence is active. There were five tagged releases between 2025-12-18 and 2026-03-04, so roughly every 1-3 weeks in that window.
- Recent releases include meaningful product work, not just dependency bumps: attached block devices, Kubernetes OIDC fields, global-region load balancer support, NAT gateway resources.
- The repo is clearly alive and product-driven.

Contributor count is the one metric I could not get cleanly from GitHub’s non-authenticated HTML in this session. A third-party package index currently reports 42 contributors for the repo, but that is not a primary source, so I would treat “dozens of contributors” as the defensible claim unless we later pull GitHub API data directly.

### Hetzner `hcloud`

Primary sources:

- Repo: <https://github.com/hetznercloud/terraform-provider-hcloud>
- Releases: <https://github.com/hetznercloud/terraform-provider-hcloud/releases>

Observed signals as of 2026-04-11:

- Latest release: `v1.60.1`, dated 2026-02-16.
- Recent prior releases: `v1.60.0` on 2026-01-29, `v1.59.0` on 2026-01-16, `v1.58.0` on 2026-01-05, `v1.57.0` on 2025-11-28, `v1.56.0` on 2025-11-10.
- Open issues visible on the repo page: 53.
- Stars/forks visible on the repo page: 701 stars, 88 forks.
- Total commits visible on the repo page: 970.
- README explicitly mentions OpenTofu support.

Interpretation:

- Release cadence is also active, again roughly every 2-3 weeks.
- The provider appears especially disciplined around compatibility management; release notes explicitly call out OpenTofu support windows, deprecations, and experimental features.
- DNS support and Storage Box support were both expanded recently, which suggests the provider is still meaningfully broadening scope.

Exact contributor count had the same GitHub access limitation here. The defensible claim from primary sources is again “dozens of contributors,” with stronger community footprint than Vultr as reflected by stars and ecosystem attention.

### Maturity comparison

If “maturity” means breadth of managed platform services, Vultr wins because the provider can manage managed K8s, managed databases, and object storage directly.

If “maturity” means provider engineering discipline and explicit OpenTofu compatibility posture, Hetzner is at least as strong and arguably stronger. The README and release notes are unusually explicit about supported OpenTofu versions and experimental features. The repo also has materially higher community visibility.

So the right phrasing is:

- Vultr provider maturity: mature enough for serious platform use, especially if you want managed cloud services.
- Hetzner provider maturity: mature and probably cleaner from an OpenTofu-provider-maintenance standpoint, but bounded by a smaller managed-service product surface.

## 4. RFQ precedent: how transferable is the pattern?

This section is partly inference because I did not inspect the RFQ repo locally under the “no subprocesses” rule. I am relying on the description in the task: “working OpenTofu for Railway (`infra/` directory with modules/environment pattern).”

Inference: that pattern is highly transferable.

The reusable parts are architectural, not provider-specific:

- `infra/modules/*` for reusable building blocks.
- `infra/environments/<env>` or equivalent roots for prod/staging/dev composition.
- Provider-agnostic naming, tagging/labeling, and secret-input conventions.
- A backend block and workspace/environment discipline that keeps state separated cleanly.

What transfers directly:

- Directory shape.
- Module interface style.
- Per-environment root modules.
- Shared variable conventions.
- CI flow around `tofu fmt`, `tofu validate`, `tofu plan`, and approval boundaries.

What does not transfer directly:

- Railway-specific resources/modules.
- Any assumptions that the provider offers PaaS-style deployment primitives.
- Any modules that collapse application deployment and infrastructure provisioning into one provider graph.

For Vultr, the RFQ pattern should port with relatively little conceptual friction because Vultr still offers enough managed resources to keep the IaC graph fairly compact.

For Hetzner, the pattern still transfers, but the module stack will be more infrastructure-heavy:

- modules for servers, networks, firewalls, load balancers, DNS, and volumes;
- separate modules or tooling for self-managed Kubernetes/bootstrap;
- separate operational story for databases and stateful services.

So the RFQ structure is transferable; the service decomposition is not.

## 5. Remote state: where should `tfstate` live?

The high-level answer is: use an S3-compatible remote backend, but prefer a state store that is operationally independent from the main compute provider unless there is a strong reason not to.

OpenTofu documents remote backends as the standard mechanism for shared state and notes that backend choice determines storage and locking behavior: <https://opentofu.org/docs/language/state/backends/> and <https://opentofu.org/docs/language/settings/backends/configuration/>. OpenTofu’s 1.10 line also introduced native S3 backend locking, reducing the historical friction around S3-style backends: <https://opentofu.org/blog/help-us-test-opentofu-1-10-0-alpha1/>.

### Option A: provider-native S3

Vultr:

- Strong option.
- Vultr Object Storage is S3-compatible, and the Terraform provider can provision object storage resources directly: <https://docs.vultr.com/reference/terraform/resources/object_storage>.
- This gives a clean one-provider bootstrap if the platform is already Vultr-first.

Hetzner:

- Technically viable because Hetzner Object Storage is S3-compatible: <https://docs.hetzner.com/storage/object-storage/faq/general>.
- Less clean operationally because Object Storage is not currently visible in the `hcloud` provider resource list, so bootstrap is partly outside `hcloud`.

### Option B: external S3-compatible state store such as Cloudflare R2 or Backblaze B2

This is the safer default recommendation.

Why:

- Keeps state independent from the target compute provider.
- Makes provider switching or multi-cloud expansion easier.
- Avoids circular bootstrap problems where you need the main provider configured in order to create the bucket that stores the main provider’s own state.
- Lets Vultr and Hetzner environments share one consistent backend pattern.

R2 is attractive if the team already uses Cloudflare. B2 is attractive if the goal is “boring object storage, minimal coupling.” Either is a stronger long-term default than embedding state inside the same provider account you are actively mutating.

## Recommendation

For a platform that wants managed Kubernetes and managed Postgres, choose Vultr and treat its provider as production-ready.

For a platform that wants cheap, solid primitives and is willing to self-manage the higher layers, Hetzner `hcloud` is mature enough, but it changes the platform scope materially.

For remote state, standardize on an external S3-compatible backend first. Use provider-native object storage only if there is a deliberate reason to keep bootstrap entirely inside the provider account.

## Sources

- Vultr provider repo: <https://github.com/vultr/terraform-provider-vultr>
- Vultr provider docs tree: <https://github.com/vultr/terraform-provider-vultr/tree/master/website/docs/r>
- Vultr releases: <https://github.com/vultr/terraform-provider-vultr/releases>
- Vultr object storage resource docs: <https://docs.vultr.com/reference/terraform/resources/object_storage>
- Vultr object storage S3 compatibility: <https://docs.vultr.com/platform/security-best-practices/vultr-object-storage>
- Hetzner provider repo: <https://github.com/hetznercloud/terraform-provider-hcloud>
- Hetzner provider resources docs tree: <https://github.com/hetznercloud/terraform-provider-hcloud/tree/main/docs/resources>
- Hetzner releases: <https://github.com/hetznercloud/terraform-provider-hcloud/releases>
- Hetzner Object Storage general FAQ: <https://docs.hetzner.com/storage/object-storage/faq/general>
- Hetzner Object Storage buckets/objects FAQ: <https://docs.hetzner.com/storage/object-storage/faq/buckets-objects>
- Hetzner “What’s New”: <https://docs.hetzner.cloud/whats-new>
- OpenTofu backend docs: <https://opentofu.org/docs/language/state/backends/>
- OpenTofu backend configuration docs: <https://opentofu.org/docs/language/settings/backends/configuration/>
- OpenTofu 1.10 S3 locking announcement: <https://opentofu.org/blog/help-us-test-opentofu-1-10-0-alpha1/>
