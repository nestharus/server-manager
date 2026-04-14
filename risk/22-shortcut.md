# Shortcut Risk Assessment: VersionedMixin

## Overall: LOW

## Findings

### Finding 1: No custom validator is a deliberate choice, not a gap
- Severity: LOW
- Description: The proposal omits custom validators on the `version`
  field, relying solely on `Field(ge=0)` for constraint enforcement.
  This could appear to be a shortcut — deferring validation to
  consumers. However, the `ge=0` constraint is the only validation
  that belongs at the contract layer. Staleness checks (comparing
  submitted version against current entity version) are service/domain
  logic, not schema validation. The Java reference confirms this
  separation: `EntityValidator.validateIsNotStale()` lives in the
  validator layer, not in the DTO definition. Adding a custom Pydantic
  validator here would either duplicate `ge=0` or pull domain logic
  into the contract layer.
- Recommendation: None. The proposal correctly places validation
  responsibility where it belongs.

### Finding 2: "Mixin" naming vs BaseModel inheritance
- Severity: LOW
- Description: The class is named `VersionedMixin` but is a
  `BaseModel` subclass, not a plain Python mixin. In Python
  convention, "mixin" implies a plain class designed for multiple
  inheritance composition. The proposal's hierarchy diagram shows
  single-inheritance chains (`BaseModel -> VersionedMixin ->
  SubmissionRead`), which is clean. The naming could invite future
  consumers to compose it via multiple inheritance with another
  `BaseModel` subclass, which would surface the multi-base config
  caveat the research identified. However, the proposal mitigates
  this by omitting `model_config` from the mixin and documenting the
  multi-base guidance explicitly.
- Recommendation: None. The naming reflects how the class is used
  (mixed into concrete contracts to add a field), the `model_config`
  omission prevents the practical risk, and the multi-base guidance
  is documented. Renaming to `VersionedBase` would be equally valid
  but is a style preference, not a risk.

### Finding 3: Proposal stays on documented Pydantic surface
- Severity: LOW
- Description: The research flagged that plain-class mixin field
  contribution in Pydantic v2 is observed but not documented. The
  proposal explicitly chose `BaseModel` inheritance instead, which is
  the primary documented composition pattern. This is not a shortcut —
  it is the correct response to the research finding. The proposal
  does not rely on any undocumented Pydantic behavior.
- Recommendation: None. The proposal addressed this research finding
  directly.

### Finding 4: Create schema separation is specified, not deferred
- Severity: LOW
- Description: The proposal says create schemas should be separate
  models that omit `version`, but does not define those create schemas.
  This could appear to defer complexity. However, create schemas are
  explicitly out of scope for this module (documented in anti-scope),
  and the separation strategy is fully specified: create models inherit
  from `BaseModel` directly, not from `VersionedMixin`. The hierarchy
  diagram makes the two branches clear. No consumer needs to figure
  out how to handle version semantics differently — versioned contracts
  inherit the mixin, create contracts don't.
- Recommendation: None. The boundary is well-defined and does not
  push decisions to consumers.
