# INIT-115 Needs Synthesis

Humility needs a local-first policy control plane that is reviewable in Git and
recoverable when Infisical is unavailable.

User-facing needs:

- Keep policy authoring close to GitOps and channel contracts.
- Prove at least one human claim and one service claim against Cedar.
- Document and script credential rotation rather than leaving deferred INIT-103
  and INIT-104 items as tribal knowledge.
- Avoid live Discord-visible changes.

Operational needs:

- The policy bundle must be rendered by the existing OPAL bootstrap path.
- Service identities must be declarative until real OIDC federation is wired.
- Break-glass recovery must re-encrypt the SOPS sentinel and restart Flux
  reconciliation without requiring Infisical.
- Operator RBAC should narrow Crossplane human access to namespaced claims.
