# INIT-118 Shortcut Risk

Risk: LOW.

No old frontend is preserved and no SPA-side OIDC fallback is introduced.
Compatibility code is isolated as a Solid 2 beta release gate, not a parallel
product path. Token flow avoids committed `.npmrc` secrets.
