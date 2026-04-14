# Risk Assessment: Chapter Contracts (`services/api/app/contracts/chapters.py`)

Date: 2026-04-13

Proposal: `proposals/26-chapters-contract.md`

## Verdict: LOW

The proposal is well-bounded and internally consistent. All six
assessment criteria pass with no blocking issues. Two findings are
recorded below for tracking; neither requires proposal revision.

## Findings

### F1. Snowflake precision risk is current, not future — Severity: LOW

The proposal states that JSON-number precision loss for JavaScript
clients applies "once values exceed `2^53 - 1`." Discord snowflakes
already exceed that threshold (`2^53 - 1` = 9,007,199,254,740,991;
current Discord IDs are in the 10^18 range). The risk is present today,
not hypothetical.

The proposal explicitly acknowledges the tension and defers it to the
API/shared-types boundary. That deferral is reasonable because:

- The Python side handles arbitrary-precision integers natively.
- The contract module is not where serialization format decisions belong.
- The project does not yet have a JavaScript/TypeScript consumer.

This finding is informational. When a web client is introduced, the
snowflake serialization decision must be revisited before Discord IDs
are served over JSON to browser consumers.

### F2. Conditional positivity constraint on nullable snowflake fields — Severity: LOW

`ChapterUpdate` declares Discord ID fields as `int | None` with the
constraint `> 0 when present`. Pydantic's `Field(gt=0)` cannot express
"greater than zero only when not None" on its own. Implementation will
require either a field-level validator or an annotated type that
short-circuits on `None` before applying the bound.

This is an implementation nuance, not a design flaw. The proposal's
intent is unambiguous — the constraint applies conditionally — but the
implementer must choose the right Pydantic mechanism. `ChapterRead` has
the same pattern for the same fields.

## Criteria Assessment

### 1. Data validation

All fields have explicit constraints:

- `name`: min 1, max 100, whitespace-trimmed, whitespace-only rejected.
- `slug`: max 50, regex `^[a-z0-9]+(?:-[a-z0-9]+)*$`, reject-don't-coerce.
- `id`: positive integer.
- `status`: closed `StrEnum`.
- Discord IDs: `int | None`, `> 0` when present.
- `created_at`: required `datetime`.
- `version`: inherited `int`, `ge=0`.

No fields are left unconstrained. Validation rules are shared across
create/read/update where field shapes overlap. **Pass.**

### 2. Snowflake handling

Discord snowflakes are typed as Python `int` with positivity guards.
This matches the repo's existing convention (`settings.py` types guild
ID as `int`). The precision concern for non-Python consumers is
explicitly acknowledged and scoped out with stated rationale. See F1 for
the timing nuance. **Pass** (with tracked finding).

### 3. Enum exhaustiveness

`ChapterStatus` is a `StrEnum` with exactly three values: `active`,
`archived`, `provisioning`. The proposal explicitly states the set is
closed and that arbitrary strings are rejected at the boundary. Status
transitions are correctly delegated to service logic, not the contract.
**Pass.**

### 4. Version field

`VersionedMixin` provides `version: int = Field(ge=0)`. The proposal
correctly applies it:

- `ChapterCreate` does not inherit it.
- `ChapterRead` inherits it (version returned to clients).
- `ChapterUpdate` inherits it (version required for optimistic locking).
- Stale-write detection is service-layer, mapped to `409 Conflict`.

This matches the Java reference pattern and the existing `base.py`
docstring. **Pass.**

### 5. Information leakage

`ChapterRead` exposes: `id`, `name`, `slug`, `status`,
`discord_category_id`, `discord_officer_role_id`,
`discord_member_role_id`, `created_at`, `version`. No passwords, tokens,
secrets, PII, or internal-only debugging fields are present. Discord
role/category IDs are infrastructure identifiers needed by clients that
interact with the Discord guild. Audit actor fields (`created_by`,
`updated_by`) are explicitly excluded in anti-scope. **Pass.**

### 6. Input validation gaps

- **Slug regex** prevents path traversal, injection, and encoding
  tricks. Only `[a-z0-9-]` with structural hyphen rules. Max length 50.
- **Name** allows Unicode (no character-class restriction beyond
  trimming). This is standard for display names in admin tools. No
  injection vector exists because the value is not interpolated into
  queries or templates at the contract layer.
- **Enum** rejects arbitrary strings.
- **Integers** reject non-numeric input.
- **Version** is non-negative bounded.
- The proposal explicitly excludes business-rule validation (uniqueness,
  state transitions, existence checks) from the contract layer, which is
  the correct boundary.

No injection or abuse vectors identified. **Pass.**

## Recommendations

None required. Both findings are tracked for implementation awareness
and future serialization decisions. The proposal may proceed to
implementation as designed.
