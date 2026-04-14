# Staging environment — small VKE cluster
environment  = "staging"
cluster_name = "humility"
region       = "ewr"          # New Jersey
worker_plan  = "vc2-1c-2gb"   # 1 vCPU, 2 GB — $10/mo
min_nodes    = 1
max_nodes    = 2
