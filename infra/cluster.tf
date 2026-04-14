locals {
  cluster_id = "${var.cluster_name}-${var.environment}"

  control_plane_nodepools = [
    {
      name        = "${local.cluster_id}-control-plane"
      server_type = var.control_plane_server_type
      location    = var.location
      labels = [
        "cluster=${var.cluster_name}",
        "environment=${var.environment}",
        "role=control-plane",
      ]
      taints = []
      count  = var.control_plane_count
    }
  ]

  agent_nodepools = [
    {
      name        = "${local.cluster_id}-worker"
      server_type = var.worker_server_type
      location    = var.location
      labels = [
        "cluster=${var.cluster_name}",
        "environment=${var.environment}",
        "role=worker",
      ]
      taints = []
      count  = var.worker_count
    }
  ]
}

module "cluster" {
  # Newer kube-hetzner releases require a newer hcloud provider line than the
  # replayed `~> 1.49` pin. v2.15.3 keeps the root module compatible.
  source  = "kube-hetzner/kube-hetzner/hcloud"
  version = "2.15.3"

  providers = {
    hcloud = hcloud
  }

  hcloud_token  = var.hcloud_token
  cluster_name  = var.cluster_name
  network_region = var.network_zone

  # The pinned module accepts one existing Hetzner SSH key id. The wrapper keeps
  # the root interface as a list so environments can stay additive.
  hcloud_ssh_key_id = length(var.ssh_key_ids) > 0 ? tostring(var.ssh_key_ids[0]) : null
  ssh_public_key    = var.ssh_public_key
  ssh_private_key   = var.ssh_private_key

  # Embedded etcd becomes HA once the control plane count reaches three; staging
  # can stay single-node while production uses the same module path.
  control_plane_nodepools = local.control_plane_nodepools
  agent_nodepools         = local.agent_nodepools

  # kube-hetzner creates the private Hetzner network and subnets around this
  # network region, so the root only needs to keep the region explicit.
  load_balancer_location = var.location
  load_balancer_type     = "lb11"
  ingress_controller     = "traefik"

  # Keep the API load balancer seam separate from the ingress controller so
  # later ingress changes do not require revisiting control plane access.
  use_control_plane_lb                  = var.control_plane_count > 1
  control_plane_lb_enable_public_interface = true

  create_kubeconfig       = false
  automatically_upgrade_os = var.control_plane_count > 1
  placement_group_disable = var.control_plane_count == 1 && var.worker_count == 1
}
