# Shortcut Risk: daemon/config.py (Revised)

**Overall risk level: LOW**

The revised proposal is thorough and internally consistent. It adds
Discord platform limit validation that was absent from the research
baseline (25 options, 4000 max_length, slug regex, chunk size 5), defines
a clean data model with frozen dataclasses, and explicitly scopes out
runtime concerns. The multi-step split algorithm matches the concrete
Dark Nemesis example in the daemon design. The findings below are places
where the Discord-limit validation pass was applied partially — the same
principle (catch platform constraint violations at config time, not at
runtime) should extend to a few more fields.

## Findings

### 1. Discord label length limits not validated (MEDIUM)

The proposal validates `label` as "non-empty string" for all question
types. Discord text input components cap `TextInput.label` at 45
characters. The proposal already enforces Discord limits for `max_length`
(4000) and `options` count (25) — omitting the label length limit is an
inconsistent application of the same principle.

Current Dark Nemesis labels range from 22 to 42 characters, so they pass
today. A future form author adding a 50-character label would pass config
validation and get a Discord API error at runtime.

**Severity:** MEDIUM — the inconsistency undermines the proposal's stated
goal of catching platform violations at load time, and the 45-character
limit is easy to exceed without realizing it.

**Recommendation:** Add a validation rule: `label` must be at most 45
characters for `short`, `long`, and `number` questions (text input
components). Select-type question labels are rendered differently (in
message content, not as a component label) so a separate limit may or may
not apply depending on the runtime rendering strategy.

### 2. Form title length unvalidated against modal title limit (LOW)

Discord modal titles are capped at 45 characters. The proposal validates
`title` as "non-empty string" with no length constraint. If `form.title`
is used as the modal title — the natural mapping given the data model —
an oversized title would fail at runtime.

The current Dark Nemesis title ("Dark Nemesis Chapter Application") is 34
characters.

**Severity:** LOW — the current title fits, and future form authors would
likely discover this quickly in testing. But it is the same class of
omission as finding 1.

**Recommendation:** Add a validation rule: `title` must be at most 45
characters.

### 3. No guard against forms with zero modal-compatible questions (LOW)

The split algorithm partitions questions into `modal_questions`
(`short`/`long`/`number`) and `select_questions`
(`select`/`multi_select`), then chunks each group into steps. If a form
contains only `select` and `multi_select` questions, `modal_questions` is
empty and the step plan contains zero modal steps.

The daemon interaction model starts with `/apply` opening a modal. With
no modal step, the runtime has nothing to present. The existing
validation rule "questions must be a non-empty list" does not catch this
because the list is non-empty — it just has no modal-compatible entries.

**Severity:** LOW — this edge case requires a form author to write a form
with exclusively select-type questions, which is unlikely but
structurally possible.

**Recommendation:** Add a validation rule: a form must contain at least
one `short`, `long`, or `number` question (i.e., at least one
modal-compatible question). This is a single check after building
`modal_questions`.

### 4. Select option label length uncapped (LOW)

Discord `SelectOption.label` is capped at 100 characters. The proposal
validates options as "non-empty strings" with no length constraint. This
is unlikely to bite in practice — current options are well under 100
characters — but it is the same class of omission as findings 1 and 2.

**Severity:** LOW — 100 characters is generous and hard to exceed
accidentally.

**Recommendation:** Add a validation rule: each option string must be at
most 100 characters.

### 5. custom_id length budget not addressed (LOW)

Discord `custom_id` fields are capped at 100 characters. The runtime
will likely compose custom_id values from form ID, question ID, and
possibly step index (e.g., `dark-nemesis:timezone:1`). The proposal
validates `id` fields as "non-empty string" with no length constraint.

**Severity:** LOW — current IDs are short slugs and the combined length
is well under 100 characters. This is more of a documentation gap than a
validation gap, since the composition scheme is a runtime concern.

**Recommendation:** Either add a length cap to `id` fields (e.g., 50
characters each), or document the 100-character custom_id budget as a
constraint that the runtime must respect. The config loader may not be
the right place to enforce this since it does not know the composition
scheme.
