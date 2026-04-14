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
  source  = "kube-hetzner/kube-hetzner/hcloud"
  version = "~> 2.0"

  providers = {
    hcloud = hcloud
  }

  hcloud_token   = var.hcloud_token
  cluster_name       = "${var.cluster_name}-${var.environment}"
  network_region = var.network_zone

  ssh_hcloud_key_ids = var.ssh_key_ids

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
