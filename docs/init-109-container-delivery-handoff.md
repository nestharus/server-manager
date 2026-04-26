# INIT-109 Handoff: CI/CD Container Delivery

INIT-108 established the registry contract and local proof path. INIT-109 can
start from these stable surfaces:

- Channel image names use `<registry>/<channel>/<app>:<tag>`.
- Local push image: `localhost:5000/local/<app>:<tag>`.
- Local cluster pull image: `k3d-humility-local:5000/local/<app>:<tag>`.
- Dev remote image: `ewr.vultrcr.com/humility/dev/<app>:<tag>`.
- Local build command lives at `infra/scripts/build-channel-image.sh`.
- Local proof harness lives at `infra/tests/validate_container_delivery_local.sh`.
- Vultr CR credentials are expected in `Secret/vultr-cr-credentials` in
  `app-runtime`, sourced from Infisical project `platform-registry`, path
  `/registry/dev`.

INIT-109 should add workflow execution only. It should not redefine the channel
schema, introduce a second registry naming convention, or move registry
credentials into SOPS.
