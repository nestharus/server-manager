# Risk Assessment: Shortcut — Backend Cleanup

## Verdict: LOW

## Findings

1. **Hardcoded values are moved, not just reshuffled (LOW)**
   The current `infra/main.tf` hardcodes `bucket`, `key` (with a literal
   `ENVIRONMENT` placeholder), and `endpoint` directly in the backend
   block. The proposal moves these three values into per-environment
   `.tfbackend` files where they become explicit, environment-scoped
   configuration inputs rather than inline literals in shared source. The
   values that remain in `main.tf` — `region = "fsn1"` and the five
   `skip_*`/`force_path_style` flags — are genuinely environment-
   independent: they describe Hetzner S3-compatibility behavior, not the
   identity of any particular state file. This is a clean separation, not
   a relocation of the same problem.

2. **Bucket name duplication across environments is intentional and correct (LOW)**
   The `bucket = "humility-terraform-state"` value appears in both
   `staging/backend.tfbackend` and `production/backend.tfbackend`. The
   proposal explicitly acknowledges this and explains the rationale:
   the bucket is part of the concrete backend selection for each
   environment and belongs alongside `key` and `endpoints`, even if the
   value happens to be identical today. This is standard `.tfbackend`
   practice — each file must be self-contained because `tofu init
   -backend-config` treats the file as the complete set of per-
   environment overrides. Extracting the bucket into a shared location
   would require a wrapper script or templating layer, which the
   proposal correctly avoids.

3. **The `ENVIRONMENT` placeholder is eliminated, not papered over (LOW)**
   The current `main.tf` contains `key = "humility/ENVIRONMENT/
   terraform.tfstate"` — a literal string that is neither a valid
   Terraform variable reference nor a real state key. It exists as a
   human-readable hint that must be manually replaced. The proposal
   removes this placeholder entirely by giving each environment its own
   explicit key (`humility/staging/terraform.tfstate` and `humility/
   production/terraform.tfstate`). No TODO markers, template tokens, or
   placeholder values survive in the proposed file content.

4. **No workarounds — the proposal fixes the root cause (LOW)**
   The root problem is that `main.tf` claims backend values should come
   from external configuration but then hardcodes them in source, making
   the comment and the code contradict each other. The proposal resolves
   this directly by making the backend block genuinely partial and
   requiring `-backend-config` at init time. It does not introduce
   wrapper scripts, environment variable interpolation, or conditional
   logic to work around the mismatch — it eliminates it.

5. **The `.tfbackend` pattern is canonical Terraform/OpenTofu practice (LOW)**
   Partial backend configuration with `-backend-config` is a first-class
   Terraform feature documented in the official backend configuration
   guide. The `.tfbackend` file extension is the conventional name for
   these files. The proposal also modernizes the endpoint declaration
   from the deprecated singular `endpoint` argument to the `endpoints`
   map form, aligning with current OpenTofu conventions. No custom
   tooling, non-standard patterns, or provider-specific hacks are
   introduced.

## Justification

The proposal introduces no shortcuts. It replaces an existing shortcut
(the `ENVIRONMENT` placeholder in `main.tf`) with the standard
`.tfbackend` partial configuration pattern. Hardcoded values are
separated into environment-scoped files rather than relocated to another
shared location. The one instance of duplication (`bucket`) is inherent
to the self-contained nature of `.tfbackend` files and is explicitly
documented. No placeholder values, TODO markers, or workarounds remain
in the proposed file content. The pattern follows established
Terraform/OpenTofu conventions exactly.
