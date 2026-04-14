# Flux System Bootstrap

The files `gotk-components.yaml` and `gotk-sync.yaml` referenced in
`kustomization.yaml` are **generated at bootstrap time**, not committed
beforehand.

## Bootstrap sequence

1. Install the Flux CLI.
2. Bootstrap Flux against this repository, for example:

   `flux bootstrap github --owner <OWNER> --repository discord --branch main --path k8s/base/flux-system`

3. Confirm the generated files now exist:

   `ls k8s/base/flux-system/gotk-components.yaml k8s/base/flux-system/gotk-sync.yaml`

Until `flux bootstrap` has run, those two files are expected to be
absent from a fresh clone.
