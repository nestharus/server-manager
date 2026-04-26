# INIT-111 Risk Gate: Shortcut

Verdict: LOW

The proposal avoids the likely shortcuts:

- it installs CNPG and Atlas from pinned upstream manifests instead of a
  floating install command;
- it stores credentials in Infisical and commits no database Secret values;
- it applies a real Atlas migration rather than checking in an already-migrated
  database image;
- it validates with `psql` and schema inspection, not only Kubernetes object
  existence;
- it leaves scheduled backups to INIT-112 instead of introducing a partial
  backup system.

No shortcut risk blocks implementation.
