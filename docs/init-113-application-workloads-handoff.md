# INIT-113 Handoff: Application Workloads

Local deployment resources live under
`gitops/channels/local/applications/server-manager`.

Build images:

```bash
bash infra/scripts/build-server-manager-images.sh \
  --channel local \
  --tag init-113-local
```

Static validation:

```bash
bash infra/tests/validate_application_workloads_local.sh --static-only
```

Runtime validation:

```bash
bash infra/tests/validate_application_workloads_local.sh \
  --channel local \
  --kubeconfig ~/.kube/humility-local.yaml
```

The runtime proof expects the local substrate to be reconciled, the app images
to be pushed to `localhost:5000`, and Infisical to contain:

- `server-manager:/runtime/local`
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
  - `SUPABASE_SERVICE_KEY`
- `platform-databases:/postgres/local/server-manager`
  - `username`
  - `password`
- `platform-storage:/object-storage/local`
  - `MINIO_ROOT_USER`
  - `MINIO_ROOT_PASSWORD`

The Discord daemon starts only after the operator supplies a real bot token.
No INIT-113 manifest sends Discord messages or mutates the live guild.

