locals {
  kubeconfig_path = pathexpand(var.kubeconfig_path)
  k3d_image_tag   = replace(var.k3s_version, "+", "-")
}

resource "null_resource" "k3d_cluster" {
  triggers = {
    channel_id      = var.channel_id
    cluster_name    = var.cluster_name
    k3s_version     = var.k3s_version
    servers         = tostring(var.servers)
    agents          = tostring(var.agents)
    registry_name   = var.registry_name
    registry_port   = tostring(var.registry_port)
    kubeconfig_path = local.kubeconfig_path
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -euo pipefail

      mkdir -p "$(dirname "$KUBECONFIG_PATH")"

      desired_nodes=$((SERVERS + AGENTS))
      existing_nodes="$(k3d node list --output json 2>/dev/null | python3 -c '
import json
import sys

cluster = sys.argv[1]
try:
    nodes = json.load(sys.stdin) or []
except Exception:
    nodes = []
print(sum(1 for node in nodes if node.get("labels", {}).get("k3d.cluster") == cluster))
' "$CLUSTER_NAME")"

      if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1 && [[ "$existing_nodes" != "$desired_nodes" ]]; then
        echo "k3d cluster '$CLUSTER_NAME' topology changed; recreating"
        k3d cluster delete "$CLUSTER_NAME"
      fi

      if k3d cluster get "$CLUSTER_NAME" >/dev/null 2>&1; then
        echo "k3d cluster '$CLUSTER_NAME' already exists with desired topology; skipping create"
      else
        k3d cluster create "$CLUSTER_NAME" \
          --image "rancher/k3s:$K3D_IMAGE_TAG" \
          --servers "$SERVERS" \
          --agents "$AGENTS" \
          --registry-create "$REGISTRY_NAME:0.0.0.0:$REGISTRY_PORT" \
          --kubeconfig-update-default=false \
          --wait
      fi

      k3d kubeconfig get "$CLUSTER_NAME" > "$KUBECONFIG_PATH"
      chmod 600 "$KUBECONFIG_PATH"
    EOT

    environment = {
      CLUSTER_NAME    = var.cluster_name
      K3D_IMAGE_TAG   = local.k3d_image_tag
      SERVERS         = tostring(var.servers)
      AGENTS          = tostring(var.agents)
      REGISTRY_NAME   = var.registry_name
      REGISTRY_PORT   = tostring(var.registry_port)
      KUBECONFIG_PATH = local.kubeconfig_path
    }
  }

  provisioner "local-exec" {
    when    = destroy
    command = "k3d cluster delete \"$CLUSTER_NAME\" || true"

    environment = {
      CLUSTER_NAME = self.triggers.cluster_name
    }
  }
}
