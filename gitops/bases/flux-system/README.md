# `flux-system` base

Active base owned by INIT-009. Hosts the Flux CD self-management manifests.

This base contains the static Flux controller install generated from the
pinned Flux CLI version in `gitops/scripts/install-tools.sh`, plus split
self-management resources:

- `source-gitrepository.yaml` defines the `server-manager` source.
- `root-kustomization.yaml` reconciles `./gitops/channels/dev`.

The conventional `gotk-sync.yaml` is intentionally omitted. The split files
make the source and root reconciliation contract explicit for validation and
for the channel-level local-source patch.
