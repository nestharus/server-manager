# Registry Smoke Image

This sample image is the INIT-108 local registry proof workload. The build
script tags it as `<registry>/<channel>/registry-smoke:<tag>`, pushes it to the
channel registry, and the cluster harness runs a Pod from the cluster pull URL.
