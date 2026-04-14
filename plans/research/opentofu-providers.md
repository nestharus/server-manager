# OpenTofu provider coverage for Hetzner/Vultr Kubernetes platform

As of 2026-04-14.

## 1. Executive summary

OpenTofu is a practical canonical IaC layer here in 2026. OpenTofu’s own docs position it as a drop-in Terraform replacement, say it preserves existing workflows and configurations, exposes thousands of providers/modules, and remains compatible with Terraform’s provider protocol. In practice, the current OpenTofu registry carries current `hetznercloud/hcloud`, `vultr/vultr`, and `kube-hetzner/kube-hetzner/hcloud` artifacts.

The split is not “OpenTofu or Kubernetes tooling”; it is “where OpenTofu stops.” OpenTofu cleanly owns cloud primitives, DNS, load balancers, volumes, buckets/accounts, managed databases where available, and the bootstrap seam into Kubernetes. It should not be the long-term owner of all in-cluster application state.

For Hetzner, the practical path is `hetznercloud/hcloud` plus the opinionated `kube-hetzner` module. That path is viable and mature enough for a robust k3s control plane, but it still depends on a Packer-built image/bootstrap step and on non-`hcloud` handling for S3-style object storage. For Vultr, the first-party provider surface is broader: VKE, extra node pools, DNS, load balancers, object storage, and managed databases are all present in the provider. That makes Vultr the cleaner OpenTofu-first platform if the goal is minimum operational tax.

## 2. Provider and module coverage table

| Area | Hetzner | Vultr | Practical read |
| --- | --- | --- | --- |
| OpenTofu and Terraform ecosystem compatibility | Strong. OpenTofu docs say it preserves existing Terraform workflows/configs, defaults to `registry.opentofu.org`, supports private registries/filesystem mirrors, and is compatible with Terraform’s provider protocol. `hcloud` and `kube-hetzner` are present in the OpenTofu registry. | Strong for the same reasons. `vultr/vultr` is present in the OpenTofu registry. | OpenTofu is credible as the default IaC layer, with the usual exception that `hashicorp/terraform` is explicitly incompatible with OpenTofu. |
| Compute, network, firewall, volumes | Strong via first-party `hcloud_server`, `hcloud_network`, `hcloud_firewall`, `hcloud_volume`, `hcloud_load_balancer`. | Strong via first-party `vultr_instance`, `vultr_vpc`, `vultr_load_balancer`, firewall resources, and storage resources. | Both cover core IaaS well. |
| DNS | Strong in 2026 via first-party `hcloud_zone`, `hcloud_zone_rrset`, `hcloud_zone_record`. Hetzner’s Cloud changelog shows DNS became generally available on 2025-11-25. | Strong via first-party `vultr_dns_domain` and `vultr_dns_record`. | DNS is clean on both platforms now. |
| Object storage | Partial. `hcloud` exposes `storage_box`, not S3 object storage. Hetzner’s object-storage docs use the MinIO provider for bucket automation. | Strong via first-party `vultr_object_storage` and `vultr_object_storage_bucket`. | Vultr is cleaner; Hetzner crosses provider boundaries. |
| Managed database coverage | No managed-database resource found in the current `hcloud` resource set. This is an inference from the current provider surface. | Strong via first-party `vultr_database` and related database resources. | Vultr is materially better for adjacent managed services. |
| Kubernetes cluster creation | No first-party Kubernetes cluster resource found in the current `hcloud` provider surface. Practical path is `kube-hetzner` or a custom bootstrap layer. | Strong via first-party `vultr_kubernetes` and `vultr_kubernetes_node_pools`. | Vultr lets OpenTofu own cluster lifecycle more directly. |
| Kubernetes bootstrap maturity | Strong enough through `kube-hetzner`: HA defaults, private networking, CSI, Longhorn, autoscaler, ingress choices, auto-upgrades, etcd S3 backups. | Strong for managed-cluster creation, but self-managed Kubernetes on Vultr still needs a separate bootstrap approach. | Hetzner has the stronger self-managed module story; Vultr has the stronger first-party managed-cluster story. |

## 3. Hetzner path

The first-party Hetzner provider is active and OpenTofu-aware. Its README explicitly says the provider is tested with Terraform or OpenTofu releases supported upstream and should work with tools that speak Terraform plugin protocol v6. The repo was updated on 2026-04-13, and the latest release is `v1.60.1` from 2026-02-16.

What OpenTofu cleanly manages on Hetzner:

- Raw cloud primitives: servers, networks, firewalls, load balancers, volumes, primary/floating IPs, placement groups.
- DNS: zones, RRsets, and records are now first-party in `hcloud`.
- Some backup/file-storage use cases: `hcloud_storage_box`.

What OpenTofu does not cleanly cover on Hetzner from the first-party provider surface:

- No first-party managed Kubernetes resource was found in the current `hcloud` resource set.
- No first-party managed-database resource was found in the current `hcloud` resource set.
- S3-style object storage is not handled by `hcloud`; Hetzner’s own object-storage docs point to the MinIO provider for bucket management.

### `kube-hetzner` maturity and fit

`kube-hetzner` is mature enough to treat as the default Hetzner path if the decision is “self-managed k3s on Hetzner.” The module is published in the OpenTofu registry, the upstream repo is active, and the latest release is `v2.19.2` from 2026-02-17. Its README explicitly calls out OpenTofu compatibility and a production-ready k3s stack with HA-by-default control planes, private networking, Cilium/Calico/Flannel options, Hetzner CSI, Longhorn, autoscaling, and etcd S3 backups.

The important boundary is that `kube-hetzner` is not “just infrastructure.” Its quick start still requires `packer`, `kubectl`, and `hcloud`, and it creates a MicroOS snapshot before `terraform/tofu apply`. That means OpenTofu can be the control entrypoint, but the full cluster bootstrap still includes one image-build/bootstrap step outside pure provider CRUD.

Minimum production-ready Hetzner path for hosting `server-manager`:

1. Use OpenTofu with `hetznercloud/hcloud` for network, firewall, load balancer, DNS, and block storage primitives.
2. Use `kube-hetzner` for the k3s control plane instead of assembling nodes and bootstrap scripts from scratch.
3. Use an S3-compatible bucket target for etcd backups and any app object-storage needs; on Hetzner that currently means a non-`hcloud` provider path for buckets.
4. Hand off app deployment and most day-2 add-ons to GitOps or Helm after cluster reachability exists.

That is practical, but it is a self-managed Kubernetes platform, not a fully first-party managed one.

## 4. Vultr path

The Vultr provider is active and broad. The repo was updated on 2026-04-09, and the latest release is `v2.30.1` from 2026-03-04. The current resource set includes `vultr_kubernetes`, `vultr_kubernetes_node_pools`, `vultr_vpc`, `vultr_load_balancer`, `vultr_dns_domain`, `vultr_dns_record`, `vultr_object_storage`, `vultr_object_storage_bucket`, and `vultr_database`.

What OpenTofu cleanly manages on Vultr:

- VKE cluster lifecycle through `vultr_kubernetes`.
- Additional worker pools through `vultr_kubernetes_node_pools`.
- Private networking, load balancers, DNS, object storage, and managed databases.

The managed-Kubernetes fit is better than Hetzner’s if the goal is “minimum production-ready platform with less platform engineering.” The `vultr_kubernetes` resource supports `ha_controlplanes`, returns the control-plane endpoint and kubeconfig, and can attach a managed firewall. Vultr’s product docs also say you can run Kubernetes either as self-managed clusters on compute instances or through VKE, and that self-managed clusters integrate with Vultr CCM and CSI.

The gap is on the self-managed path: I did not find a `kube-hetzner`-class OpenTofu module or an equivalent first-party self-managed bootstrap stack in the official sources reviewed. So on Vultr, OpenTofu is strongest when paired with VKE. If you reject managed Kubernetes and want self-managed k3s on Vultr, OpenTofu can still own instances and networking, but a separate cluster bootstrap/tooling layer is still required.

Minimum production-ready Vultr path for hosting `server-manager`:

1. Use OpenTofu with `vultr/vultr` to create VKE with `ha_controlplanes = true`, plus any extra node pools.
2. Keep adjacent stateful services on first-party managed services where that reduces operational load, especially `vultr_database` and `vultr_object_storage`.
3. Add only the bootstrap essentials after cluster creation: ingress, certificates, and a GitOps controller.

That is the cleanest OpenTofu-first route of the two platforms.

## 5. Risks and caveats

- OpenTofu compatibility with the Terraform ecosystem is strong, but not absolute. OpenTofu explicitly warns that `hashicorp/terraform` is not compatible and should not be declared.
- Hetzner’s self-managed Kubernetes path depends heavily on `kube-hetzner`, which is opinionated and community-maintained. That is workable, but it is a different risk profile from a first-party managed control plane.
- `kube-hetzner` still has a nontrivial bootstrap seam: Packer image creation and local tooling are part of the path.
- Hetzner’s object-storage story is workable but not first-party in `hcloud`; that adds one provider boundary. Hetzner’s object-storage docs also say the service is currently available only in European locations, which matters if the cluster footprint is US-based.
- Vultr’s VKE provider surface is broad, but it is still not “everything.” The cluster resource only owns one default node pool; extra pools are separate resources.
- Vultr’s object-storage bucket resources treat some updates as destroy/recreate operations.
- As of Vultr’s 2025-12-18 support docs, VKE also had networking constraints around legacy VPC versus VPC 2.0. That needs a fresh implementation-time check against the exact network design.

## 6. Recommendation

Use OpenTofu as the canonical IaC layer.

If the goal is the minimum production-ready path with the cleanest first-party provider coverage, prefer Vultr and let OpenTofu manage VKE, DNS, load balancers, object storage, and managed databases. That is the shortest path to a cluster that can host `server-manager` without building a large amount of platform glue.

If the goal is lower raw infrastructure cost and deliberate acceptance of self-managed k3s, Hetzner is still viable. In that case, use `hetznercloud/hcloud` plus `kube-hetzner`; do not reinvent the bootstrap stack from raw instances unless there is a specific reason to own that complexity. Accept that Packer/bootstrap and non-`hcloud` object-storage handling remain part of the path.

Operationally, the right boundary is:

- OpenTofu owns the cloud substrate and the bootstrap seam.
- GitOps or Helm owns most in-cluster application lifecycle after the cluster becomes reachable.

## Sources

- OpenTofu homepage: <https://opentofu.org/>
- OpenTofu provider requirements: <https://opentofu.org/docs/v1.9/language/providers/requirements/>
- OpenTofu functions docs: <https://opentofu.org/docs/language/functions/>
- OpenTofu registry API, `hetznercloud/hcloud`: <https://registry.opentofu.org/v1/providers/hetznercloud/hcloud/versions>
- OpenTofu registry API, `vultr/vultr`: <https://registry.opentofu.org/v1/providers/vultr/vultr/versions>
- OpenTofu registry API, `kube-hetzner/kube-hetzner/hcloud`: <https://registry.opentofu.org/v1/modules/kube-hetzner/kube-hetzner/hcloud/versions>
- Hetzner provider README: <https://raw.githubusercontent.com/hetznercloud/terraform-provider-hcloud/main/README.md>
- Hetzner provider resource docs index: <https://api.github.com/repos/hetznercloud/terraform-provider-hcloud/contents/docs/resources?ref=main>
- Hetzner Cloud changelog: <https://docs.hetzner.cloud/changelog>
- Hetzner storage-box resource doc: <https://raw.githubusercontent.com/hetznercloud/terraform-provider-hcloud/main/docs/resources/storage_box.md>
- Hetzner object-storage overview: <https://docs.hetzner.com/storage/object-storage/overview/>
- Hetzner bucket creation via MinIO provider: <https://docs.hetzner.com/storage/object-storage/getting-started/creating-a-bucket-minio-terraform/>
- `kube-hetzner` README: <https://raw.githubusercontent.com/mysticaltech/terraform-hcloud-kube-hetzner/master/README.md>
- `kube-hetzner` releases: <https://github.com/mysticaltech/terraform-hcloud-kube-hetzner/releases/latest>
- Vultr provider README: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/README.md>
- Vultr provider resource docs index: <https://api.github.com/repos/vultr/terraform-provider-vultr/contents/website/docs/r?ref=master>
- Vultr Kubernetes resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/kubernetes.html.markdown>
- Vultr object storage resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/object_storage.html.markdown>
- Vultr object storage bucket resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/object_storage_bucket.html.markdown>
- Vultr database resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/database.html.markdown>
- Vultr Kubernetes support overview: <https://docs.vultr.com/support/products/vke/can-i-run-kubernetes-on-vultr>
- Vultr VKE and VPC 2.0 support note: <https://docs.vultr.com/support/products/vke/can-i-connect-my-vke-cluster-to-a-vpc2-network>
