# INIT-119 Full-Stack Infra E2E

Run locally:

```bash
infra/tests/e2e/run-fullstack.sh
```

The harness deletes and recreates the `humility-local` k3d cluster, builds the
local images, runs the 19 cross-cutting tests, writes artifacts under
`.tmp/init-119-e2e/`, writes diagnostics under
`.tmp/init-119-bringup-diagnostics/`, updates `docs/infra-e2e-status.md`, and
then deletes the cluster plus local registry/cache containers.

Expected optional secrets:

- `BUILDKITE_AGENT_TOKEN`: required for `10-buildkite` to prove the in-cluster
  Buildkite agent. Without it, that flow skips with an explicit reason.
- `DISCORD_BOT_TOKEN`: optional for local E2E. Without it, the harness seeds a
  synthetic token and the local Discord deployment runs with `DISCORD_DRY_RUN=1`.
- `FA_USERNAME`, `FA_PASSWORD`, `WA_USERNAME`, `WA_PASSWORD`: reserved for
  dashboard token bootstrap. INIT-119 does not require them for the local web
  image because no token material is committed or read by default.

Buildkite entrypoint:

```bash
buildkite-agent pipeline upload .buildkite/e2e-fullstack.yml
```
