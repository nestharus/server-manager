# INIT-110 Risk Gate: Shortcut

Verdict: LOW

The proposal avoids the likely shortcuts:

- it renders the upstream Kong Helm chart instead of hand-building a parallel
  install;
- it commits the render values, not just the generated YAML;
- it reuses INIT-105 cert-manager and DNS rather than adding a local exception;
- it validates HTTPS through Kong to a real backend instead of stopping at
  `kubectl apply --dry-run`.

No shortcut risk blocks implementation.
