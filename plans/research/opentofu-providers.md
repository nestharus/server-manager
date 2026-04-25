> **Evidence note.** Active INIT-008 authority lives in `.pipeline/proposal.md` and `DECISIONS.md` D7. Earlier bucket-resource claims in this research have been superseded by the operator-managed bucket-existence contract; do not treat this file as authority for bucket lifecycle or channel-root design.

# OpenTofu provider coverage for Vultr platform bootstrap

As of 2026-04-14.

## 1. Executive summary

OpenTofu is a practical canonical IaC layer for INIT-008. OpenTofu's own
documentation positions it as a Terraform-compatible workflow with provider
registry support and compatibility with Terraform's provider protocol. The
current OpenTofu registry carries the `vultr/vultr` provider, and the repo's
active infrastructure already targets Vultr VPC, VKE, and Object Storage.

For INIT-008, the relevant boundary is where OpenTofu stops:

- OpenTofu owns cloud substrate authoring: VPC, VKE, Object Storage
  subscription handoff, remote-state backend configuration, and provider
  lock posture.
- Channel scripts own YAML inheritance resolution and deterministic generation
  of channel-root inputs.
- GitOps or later platform initiatives own in-cluster application lifecycle
  after a cluster exists.

This supports the D7 decision: Vultr plus OpenTofu is the Phase 5 platform
bootstrap substrate, with local-only verification and no provider-backed
mutation in this slice.

## 2. Vultr provider coverage

The Vultr provider is active and broad enough for the platform-bootstrap
surface. The resource set reviewed for the original research included:

- `vultr_kubernetes`
- `vultr_kubernetes_node_pools`
- `vultr_vpc`
- `vultr_load_balancer`
- `vultr_dns_domain`
- `vultr_dns_record`
- `vultr_object_storage`
- `vultr_database`

The `vultr_kubernetes` resource is the central fit for INIT-008 because it
lets OpenTofu author the managed VKE control plane, worker-pool baseline,
control-plane endpoint output, kubeconfig output, high-availability control
planes, and managed firewall attachment. Existing modules in this repo already
model the VPC and VKE pieces around that provider.

## 3. Object Storage and state

The active INIT-008 design does not rely on an OpenTofu-managed bucket
lifecycle. The bootstrap root owns the Vultr Object Storage subscription
handoff and emits sensitive operator outputs. Bucket existence for
`humility-tfstate` is an explicit operator verification step before backend
initialization.

That posture is intentional:

- It matches the live bootstrap root.
- It avoids carrying stale resource assumptions into the channel-root design.
- It keeps SLICE-025 through SLICE-030 local-only unless an operator supplies
  credentials for a read-only plan.

## 4. Recommendation

Use OpenTofu as the canonical IaC layer for INIT-008 and use the Vultr
provider with constraint `~> 2.30`. Keep root `required_version` at
`>= 1.8.0`, while verifying INIT-008 with OpenTofu CLI `1.11.5`.

The operational boundary remains:

- OpenTofu owns cloud substrate and backend handoff inputs.
- Channel scripts own channel inheritance and generated root artifacts.
- Later initiatives own GitOps, ingress, secrets, application workloads,
  data-plane services, auth, and observability.

## Sources

- OpenTofu homepage: <https://opentofu.org/>
- OpenTofu provider requirements: <https://opentofu.org/docs/v1.9/language/providers/requirements/>
- OpenTofu functions docs: <https://opentofu.org/docs/language/functions/>
- OpenTofu registry API, `vultr/vultr`: <https://registry.opentofu.org/v1/providers/vultr/vultr/versions>
- Vultr provider README: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/README.md>
- Vultr provider resource docs index: <https://api.github.com/repos/vultr/terraform-provider-vultr/contents/website/docs/r?ref=master>
- Vultr Kubernetes resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/kubernetes.html.markdown>
- Vultr object storage resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/object_storage.html.markdown>
- Vultr database resource doc: <https://raw.githubusercontent.com/vultr/terraform-provider-vultr/master/website/docs/r/database.html.markdown>
- Vultr Kubernetes support overview: <https://docs.vultr.com/support/products/vke/can-i-run-kubernetes-on-vultr>
- Vultr VKE and VPC 2.0 support note: <https://docs.vultr.com/support/products/vke/can-i-connect-my-vke-cluster-to-a-vpc2-network>
