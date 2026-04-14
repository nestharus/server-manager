# Risk Assessment: Scope — Backend Cleanup

## Verdict: LOW

## Findings

1. **Proportional to the problem (LOW).** The current `infra/main.tf`
   hardcodes `bucket`, `key` (with a literal `ENVIRONMENT` placeholder),
   and the deprecated singular `endpoint` argument directly in the backend
   block, contradicting its own comment that says concrete values should
   come from external config. The proposal fixes exactly this mismatch by
   extracting those three values into per-environment `.tfbackend` files.
   No additional refactoring, module restructuring, or provider changes
   are included. The change is the minimum edit that closes the gap.

2. **No meaningful downstream work created (LOW).** The proposal
   explicitly excludes CI/CD initialization logic, wrapper scripts, and
   operator workflow changes. After implementation, the only new
   requirement is that operators pass `-backend-config=` during
   `tofu init`, which is standard OpenTofu practice and already implied
   by the existing comment in `main.tf`. No other Terraform files change,
   no modules are affected, and no provider versions are bumped.

3. **No blocking or debt introduced (LOW).** The `.tfbackend` pattern is
   the idiomatic OpenTofu approach for environment-specific backends.
   Future work — adding a third environment, wiring CI initialization, or
   migrating to a different state backend — can proceed additively by
   creating a new `.tfbackend` file or updating the existing ones. Nothing
   in this proposal constrains or complicates later changes to the
   infrastructure layout.

4. **Completeness is adequate (LOW).** The proposal addresses every
   environment-specific value currently embedded in the backend block:
   `bucket`, `key`, and `endpoint` (migrated to the `endpoints` map
   form). The six compatibility flags that are stable across environments
   remain in `main.tf` where they belong. Credentials are correctly left
   to environment variables. The only follow-on implied is that CI/CD
   pipelines will eventually need to pass the correct `-backend-config`
   flag, but that is an operational concern deferred to the CI/CD
   proposal — not a gap in this design.

5. **No scope creep (LOW).** The proposal does not introduce new
   providers, modules, variables, outputs, wrapper scripts, or
   automation. It does not reorganize the directory structure beyond
   placing two small files beside the existing `terraform.tfvars` files
   in the environment directories. The `endpoint` → `endpoints` map
   migration is the only change beyond a pure extraction, and it is
   justified: `endpoint` is deprecated in OpenTofu's S3 backend, so
   preserving it would create immediate tech debt.

## Justification

This is a minimal, well-scoped configuration cleanup. It produces two
new files totaling roughly six lines each, removes three hardcoded values
from `main.tf`, and migrates one deprecated argument to its current form.
The repository already has the directory structure this proposal targets
(`infra/environments/staging/` and `infra/environments/production/` both
exist with `terraform.tfvars` files), so the `.tfbackend` files slot into
an established layout.

Every exclusion is explicit: no CI/CD changes, no credential handling
changes, no module restructuring. The downstream work is limited to
eventual CI integration of the `-backend-config` flag, which is additive
and independent.

The scope is proportional, complete, and free of creep.
