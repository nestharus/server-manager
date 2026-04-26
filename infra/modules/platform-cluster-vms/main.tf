locals {
  name_prefix   = "humility-${var.channel_id}"
  firewall_name = coalesce(var.firewall_name, "${local.name_prefix}-k3s")
  server_hostnames = [
    for index in range(var.server_count) :
    "${local.name_prefix}-server-${index + 1}"
  ]
  agent_hostnames = [
    for index in range(var.agent_count) :
    "${local.name_prefix}-agent-${index + 1}"
  ]
  allowed_ssh_cidr_rules = {
    for cidr in var.allowed_ssh_cidrs : cidr => {
      subnet      = split("/", cidr)[0]
      subnet_size = tonumber(split("/", cidr)[1])
    }
  }
  ubuntu_2204_os_id = 1743
}

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

resource "vultr_firewall_group" "k3s" {
  description = local.firewall_name
}

resource "vultr_firewall_rule" "ssh" {
  for_each = local.allowed_ssh_cidr_rules

  firewall_group_id = vultr_firewall_group.k3s.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = each.value.subnet
  subnet_size       = each.value.subnet_size
  port              = "22"
  notes             = "ssh ${each.key}"
}

resource "vultr_firewall_rule" "k3s_api" {
  for_each = local.allowed_ssh_cidr_rules

  firewall_group_id = vultr_firewall_group.k3s.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = each.value.subnet
  subnet_size       = each.value.subnet_size
  port              = "6443"
  notes             = "k3s api ${each.key}"
}

resource "vultr_instance" "server" {
  count = 1

  region            = var.region
  plan              = var.server_plan
  os_id             = local.ubuntu_2204_os_id
  label             = local.server_hostnames[0]
  hostname          = local.server_hostnames[0]
  tags              = [var.channel_id, local.name_prefix, "k3s", "server"]
  ssh_key_ids       = var.ssh_key_ids
  vpc_ids           = [var.vpc_id]
  firewall_group_id = vultr_firewall_group.k3s.id

  user_data = templatefile("${path.module}/cloud-init/k3s-server.yaml.tftpl", {
    hostname               = local.server_hostnames[0]
    k3s_version            = var.k3s_version
    k3s_token              = random_password.k3s_token.result
    k3s_url_env            = ""
    k3s_exec_args          = "server --cluster-init"
    k3s_service_name       = "k3s.service"
    remote_kubeconfig_path = var.remote_kubeconfig_path
  })
}

resource "vultr_instance" "server_joiner" {
  count = var.server_count - 1

  region            = var.region
  plan              = var.server_plan
  os_id             = local.ubuntu_2204_os_id
  label             = local.server_hostnames[count.index + 1]
  hostname          = local.server_hostnames[count.index + 1]
  tags              = [var.channel_id, local.name_prefix, "k3s", "server"]
  ssh_key_ids       = var.ssh_key_ids
  vpc_ids           = [var.vpc_id]
  firewall_group_id = vultr_firewall_group.k3s.id

  user_data = templatefile("${path.module}/cloud-init/k3s-server.yaml.tftpl", {
    hostname               = local.server_hostnames[count.index + 1]
    k3s_version            = var.k3s_version
    k3s_token              = random_password.k3s_token.result
    k3s_url_env            = "K3S_URL=https://${vultr_instance.server[0].internal_ip}:6443"
    k3s_exec_args          = "server --server https://${vultr_instance.server[0].internal_ip}:6443"
    k3s_service_name       = "k3s.service"
    remote_kubeconfig_path = var.remote_kubeconfig_path
  })
}

resource "vultr_instance" "agent" {
  count = var.agent_count

  region            = var.region
  plan              = var.agent_plan
  os_id             = local.ubuntu_2204_os_id
  label             = local.agent_hostnames[count.index]
  hostname          = local.agent_hostnames[count.index]
  tags              = [var.channel_id, local.name_prefix, "k3s", "agent"]
  ssh_key_ids       = var.ssh_key_ids
  vpc_ids           = [var.vpc_id]
  firewall_group_id = vultr_firewall_group.k3s.id

  user_data = templatefile("${path.module}/cloud-init/k3s-server.yaml.tftpl", {
    hostname               = local.agent_hostnames[count.index]
    k3s_version            = var.k3s_version
    k3s_token              = random_password.k3s_token.result
    k3s_url_env            = "K3S_URL=https://${vultr_instance.server[0].internal_ip}:6443"
    k3s_exec_args          = "agent"
    k3s_service_name       = "k3s-agent.service"
    remote_kubeconfig_path = var.remote_kubeconfig_path
  })
}
