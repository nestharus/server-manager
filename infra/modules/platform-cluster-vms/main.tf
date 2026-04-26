locals {
  server_hostnames = [
    for index in range(var.server_count) :
    "${var.cluster_name}-server-${index + 1}"
  ]
  agent_hostnames = [
    for index in range(var.agent_count) :
    "${var.cluster_name}-agent-${index + 1}"
  ]

  first_server_url = "https://${local.server_hostnames[0]}:6443"
}

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

resource "vultr_instance" "server" {
  count = var.server_count

  region      = var.region
  plan        = var.server_plan
  os_id       = var.os_id
  label       = local.server_hostnames[count.index]
  hostname    = local.server_hostnames[count.index]
  tags        = [var.channel_id, var.cluster_name, "k3s", "server"]
  ssh_key_ids = var.ssh_key_ids
  vpc_ids     = [var.vpc_id]

  user_data = templatefile("${path.module}/cloud-init/k3s-server.yaml.tftpl", {
    hostname         = local.server_hostnames[count.index]
    k3s_version      = var.k3s_version
    k3s_token        = random_password.k3s_token.result
    k3s_url_env      = count.index == 0 ? "" : "K3S_URL=${local.first_server_url}"
    k3s_exec_args    = count.index == 0 ? "server --cluster-init" : "server --server ${local.first_server_url}"
    k3s_service_name = "k3s.service"
  })
}

resource "vultr_instance" "agent" {
  count = var.agent_count

  region      = var.region
  plan        = var.agent_plan
  os_id       = var.os_id
  label       = local.agent_hostnames[count.index]
  hostname    = local.agent_hostnames[count.index]
  tags        = [var.channel_id, var.cluster_name, "k3s", "agent"]
  ssh_key_ids = var.ssh_key_ids
  vpc_ids     = [var.vpc_id]

  user_data = templatefile("${path.module}/cloud-init/k3s-server.yaml.tftpl", {
    hostname         = local.agent_hostnames[count.index]
    k3s_version      = var.k3s_version
    k3s_token        = random_password.k3s_token.result
    k3s_url_env      = "K3S_URL=${local.first_server_url}"
    k3s_exec_args    = "agent"
    k3s_service_name = "k3s-agent.service"
  })
}
