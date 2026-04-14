# Hookpoint Research: K8s GitOps Manifests (NN=32)

## Context

You are mapping a proposal to existing code. Read:
- `proposals/32-k8s-manifests.md` — the approved proposal
- The existing k8s directory structure under `k8s/`

## Task

For each file in the proposal, determine:

1. **What exists already?**
   - Check `k8s/base/monitoring/` for existing kustomization, namespace, helmrepository files
   - Check `k8s/base/secrets/` for existing kustomization, namespace, helmrepository files
   - Check `k8s/base/flux-system/` for any existing files
   - Check `k8s/overlays/staging/` for any existing files

2. **What needs to be created?**
   - `k8s/base/flux-system/kustomization.yaml` — new
   - `k8s/base/monitoring/helmrelease.yaml` — new
   - `k8s/base/secrets/helmrelease.yaml` — new
   - `k8s/overlays/staging/kustomization.yaml` — new

3. **What's reusable?**
   - Do the existing base files (namespace, helmrepository) align with
     the proposal?
   - Are there patterns in the infra/ Terraform files that inform the
     k8s manifest structure?

4. **What to delete?**
   - Identify any pre-existing files that conflict with the proposal

## Anti-goals

- Do NOT write implementation code
- Do NOT modify existing files

## Output

Write findings to `research/32-hookpoints.md`.
