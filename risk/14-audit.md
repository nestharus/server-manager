# Audit Risk Assessment: daemon/config.py (Revised)

## Overall: LOW

The revised proposal addresses all MEDIUM/HIGH findings from the first
audit. Slug validation uses an explicit regex that prevents path
traversal. Discord platform limits are enforced at load time: max_length
capped at 4000, select options capped at 25, action-row chunks capped
at 5. Reload failure semantics are documented with clear caller
responsibility. The Dark Nemesis form has been trimmed to 25 timezone
options. All remaining findings are low severity and defensive in
nature.

## Prior Findings — Resolved

| Prior finding | Resolution |
|---|---|
| Slug regex missing — path traversal possible | `^[a-z0-9]+(-[a-z0-9]+)*$` blocks `/`, `\`, `..`, whitespace, dots |
| max_length unbounded | Capped at 4000 (Discord text input maximum) |
| Select options unbounded | Capped at 25 (Discord select menu limit) |
| Follow-up select chunks unbounded | Capped at 5 per chunk (Discord action-row-per-message limit) |
| Reload failure semantics undocumented | Caller retains previous config; loader raises ConfigError |
| Dark Nemesis form had 27 timezone options | Trimmed to 25 |

## Findings

### Finding 1: Discord component-level string limits not validated
- Severity: LOW
- Description: The proposal validates `max_length <= 4000` and
  `len(options) <= 25`, but does not validate Discord's string-length
  limits on other fields: modal/form `title` (max 45 chars), text input
  `label` (max 45 chars), select option labels (max 100 chars), and
  custom_id (max 100 chars). A label exceeding 45 characters would pass
  config validation but fail at the Discord API at runtime.
- Impact: Operator sees a runtime Discord API error instead of a
  load-time config error. No security or data-integrity impact.
- Recommendation: Consider adding string-length caps for `title`,
  `label`, and option values in a future pass. Not blocking — the
  failure mode is a clear Discord API error, not silent corruption.

### Finding 2: No minimum modal-question requirement
- Severity: LOW
- Description: The proposal requires `questions` to be a non-empty list
  but does not require at least one modal-compatible question (short,
  long, or number). A form consisting entirely of select/multi_select
  questions would produce zero modal steps and only followup_selects
  steps. The runtime interaction flow (which starts with a modal) would
  need to handle this edge case.
- Impact: The config loader produces a valid step plan, but the runtime
  would need special handling for the zero-modal case. This is a runtime
  concern, not a config-loader concern.
- Recommendation: Either validate at least one modal question at load
  time, or document the zero-modal case as a valid step plan that the
  runtime must handle. Not blocking.

### Finding 3: No upper bound on total question count
- Severity: LOW
- Description: The proposal validates per-step limits (5 questions per
  modal, 5 selects per action-row group) but does not cap the total
  number of questions in a form. A form with 50 questions would produce
  10+ steps, creating a long multi-step interaction. This is impractical
  but not invalid.
- Impact: Poor UX for applicants, not a security or reliability issue.
  Operator judgment is the appropriate control here.
- Recommendation: No action required. A total-question cap would be
  arbitrary and is better handled by operator review of the form.

### Finding 4: Question ID format not constrained
- Severity: LOW
- Description: The proposal requires question IDs to be unique non-empty
  strings but does not constrain their format. Since question IDs will
  likely be embedded in Discord custom_ids at runtime (max 100 chars,
  used for interaction routing), IDs containing spaces, special
  characters, or excessive length could cause runtime issues.
- Impact: The config loader accepts IDs the runtime may struggle with.
  Not a security issue — custom_ids are not user-facing.
- Recommendation: Consider applying a format constraint (e.g., the same
  slug regex, or `^[a-z0-9_]+$`) to question IDs. Low priority.

### Finding 5: Discord snowflake ID validation is minimal
- Severity: LOW
- Description: The proposal validates Discord IDs as "positive integers"
  but does not check upper bounds or snowflake structure. A typo like
  `category_id: 999` would pass validation but fail at runtime when
  Discord cannot resolve the ID. This is expected — the config loader
  validates structure, not Discord-side existence.
- Impact: Invalid IDs produce clear runtime errors when the bot attempts
  to use them. No silent failure path.
- Recommendation: No action required. Validating ID existence would
  require Discord API calls, which is explicitly anti-scope.

### Finding 6: safe_load is the correct YAML loader
- Severity: LOW (positive finding)
- Description: The research confirms `yaml.safe_load()` is used, which
  resolves only basic YAML tags and is safe for untrusted input. The
  proposal does not use `full_load` or `unsafe_load`. Combined with the
  single-document expectation (not `safe_load_all`), this is the correct
  choice.
- Recommendation: No action required.

### Finding 7: Immutable dataclasses prevent mutation bugs
- Severity: LOW (positive finding)
- Description: The proposal specifies `frozen=True` dataclasses and
  tuple (not list) for collection fields. This prevents accidental
  mutation of loaded config by runtime code, eliminating a class of
  reload-related bugs where stale references could be modified.
- Recommendation: No action required.

### Finding 8: Cross-file consistency rule is sound
- Severity: LOW (positive finding)
- Description: The rule that `form.id == chapter slug == form filename
  stem` eliminates identifier drift. The closed-schema validation
  (unknown keys rejected) prevents config typos from being silently
  ignored. Both are good defensive practices.
- Recommendation: No action required.
