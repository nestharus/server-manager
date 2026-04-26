# INIT-113 Risk: Audit

Rating: **LOW**

The proposal deploys existing service entrypoints and uses established platform
primitives. The highest-risk action is live Discord login, but INIT-113 does
not send any Discord messages or mutate server state; the daemon only starts
after the operator supplies a real token through Infisical. No Tier 3 Discord
action is introduced.

Controls:

- Runtime secrets are InfisicalSecret resources only.
- API health proof is unauthenticated and read-only.
- Database is a dedicated CNPG cluster, not the sample app cluster.
- Backups use the same CNPG barmanObjectStore pattern as INIT-112.
