# Kong Render

Kong is rendered from the upstream Helm chart and committed as raw GitOps YAML.

Regenerate after changing `render-values.yaml`:

```bash
helm repo add kong https://charts.konghq.com
helm repo update
helm template kong kong/kong \
  --version 3.2.0 \
  --namespace kong-system \
  --include-crds \
  -f gitops/channels/local/ingress/kong/render-values.yaml \
  > gitops/channels/local/ingress/kong/rendered/kong-3.2.0.yaml
```

The rendered file intentionally disables the Kong admission webhook so no
chart-generated TLS private keys are committed.
