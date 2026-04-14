# Production environment — VKE cluster with autoscaling
environment  = "production"
cluster_name = "humility"
region       = "ewr"          # New Jersey
worker_plan  = "vc2-2c-4gb"   # 2 vCPU, 4 GB — $20/mo
min_nodes    = 3
max_nodes    = 6
