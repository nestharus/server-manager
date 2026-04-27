# INIT-117 Phase 2 Synthesis

Humility needs the observability stack to cap Phase 5 by proving that the local channel is inspectable as a real deployment. The useful substrate is not a production incident program yet; it is a working local control loop with metrics, logs, alerts, and dashboards.

The implementation should therefore:

- Put all observability resources under `gitops/channels/local/observability`.
- Add a strict `observability` channel block in `infra/channels/local.yaml`.
- Use MinIO for Loki object storage and Infisical for Grafana/Loki runtime secrets.
- Keep dashboards tenant-aware through `platform.humility.gg/tenant`.
- Add a focused static and runtime harness instead of relying on manual screenshots.
- Update Phase 5 documentation to say the substrate is complete locally and remote apply remains post-INIT-117 work.

Open gap accepted for post-INIT-117 deployment: rich production SLOs, incident routing, and remote observability hardening need live remote traffic and operator preferences.
