# INIT-113 Risk: Shortcut

Rating: **LOW**

The main shortcut risk is a fake deployment proof that only renders YAML.
The proposed harness avoids that by checking runtime state when a local k3d
cluster is available: API rollout, readiness endpoint, database migration
revision, Kong HTTPS curl, and Discord Deployment/Pod presence.

The second shortcut risk is bypassing INIT-108 with hand-built image names.
The wrapper script delegates every image build to `build-channel-image.sh`, so
push and pull names remain centralized.

The third shortcut risk is hard-coded credentials. Static scans reject common
secret literals and the manifests source runtime, database, and object-storage
credentials through InfisicalSecret resources.
