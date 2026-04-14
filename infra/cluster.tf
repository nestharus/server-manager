# Vultr Kubernetes Engine (VKE) — managed control plane, free.
# We pay only for worker nodes. No kube-hetzner needed.

resource "vultr_kubernetes" "cluster" {
  region           = var.region
  label            = "${var.cluster_name}-${var.environment}"
  ha_controlplanes = var.environment == "production"

  node_pools {
    node_quantity = var.min_nodes
    plan          = var.worker_plan
    label         = "${var.cluster_name}-${var.environment}-workers"
    auto_scaler   = var.max_nodes > var.min_nodes
    min_nodes     = var.min_nodes
    max_nodes     = var.max_nodes
  }
}
