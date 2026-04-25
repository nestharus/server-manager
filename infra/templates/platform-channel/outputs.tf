output "vpc_id" {
  value = module.network.vpc_id
}

output "cluster_id" {
  value = module.cluster.cluster_id
}

output "endpoint" {
  value = module.cluster.endpoint
}
