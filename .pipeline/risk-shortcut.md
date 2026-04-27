# INIT-117 Shortcut Risk

Verdict: LOW.

No compatibility shim, feature flag, HelmRelease, or credential literal is introduced. ServiceMonitor resources are explicit API contracts while raw Prometheus config performs local scraping, which avoids adding an unscoped operator. Loki uses MinIO and Infisical-managed credentials rather than local filesystem persistence or checked-in secrets.
