# Scope Risk: daemon/config.py YAML Config Loader

**Overall risk level: LOW**

The proposal defines a focused, pure config-loading module with a small
public API (two load functions, five dataclasses, three exception types)
and an unusually thorough anti-scope section that explicitly excludes
eleven categories of runtime behavior. The revised version correctly
incorporates Discord platform limits — 25 options per select menu, 4000
max_length for text inputs, 5 components per modal, 5 action rows per
follow-up message, and a slug regex that prevents path traversal — without
expanding the module's responsibilities. Every validation rule is
individually simple and deterministic. The split algorithm is
fully specified with a concrete worked example that matches the existing
Dark Nemesis form. No new dependencies are introduced (PyYAML is already
declared in `pyproject.toml`, dataclasses are stdlib). The module
produces immutable frozen dataclasses, holds no mutable state, and
delegates all error-recovery policy to the caller.

## Findings

### 1. Validation rule count is high but proportionate

**Severity: INFO**

The proposal specifies roughly 40 individual validation rules across
file-level, chapters, forms, questions, and cross-file checks. Each rule
is simple (type check, regex match, range bound, uniqueness constraint),
and the rules group naturally into the five dataclass shapes. The density
reflects the problem — rejecting bad config at load time requires
checking every field. No rule introduces branching complexity or
dependencies on external state.

### 2. Timezone select sits at the 25-option ceiling

**Severity: INFO**

The Dark Nemesis `timezone` select has exactly 25 options, which is the
Discord maximum validated by the proposal. This is valid but leaves zero
headroom. If a future form author adds a 26th timezone option, the
loader will correctly reject it with a validation error. This is the
intended behavior — the limit is a platform constraint, not an arbitrary
choice. No action needed; noting for awareness.

### 3. Cross-file constraint (form.id == chapter slug) is narrow

**Severity: LOW**

The proposal requires `form.id` to match the chapter slug and the form
filename stem. This introduces a three-way consistency invariant. The
risk is that this constraint is easy to violate during manual YAML
editing. However, the constraint is simple to validate (string equality),
the error message will include both values and both file paths, and the
alternative — allowing drift between three identifiers — creates worse
problems downstream. The `load_form_config()` standalone function
correctly cannot enforce this check (it has no chapter context), which
is acknowledged by its description as an "isolation" loader.

### 4. Anti-scope is explicit and well-calibrated

**Severity: INFO**

The anti-scope lists eleven exclusions: Discord API calls, SQLite,
environment variables, slash-command logic, modal submission handling,
select-menu handling, numeric answer parsing, default answer values,
auto-creation of missing files, auto-discovery of orphan forms, and
mutable global registries. Each exclusion corresponds to a real design
temptation that would expand the module's role. The `number` type
boundary is particularly well-drawn — the loader preserves the type tag
but explicitly defers numeric coercion to `daemon.applications`.

### 5. Hot-reload design avoids hidden coupling

**Severity: INFO**

The proposal specifies no module-level caches, no singleton, no file
watchers, and full reconstruction on every `load_config()` call. This
makes the reload path trivially correct (call the function again) and
avoids stale-state bugs. The error-recovery policy (caller retains
previous good config on failure) is explicitly assigned to `daemon.py`,
not to this module. No scope leakage into lifecycle management.

### 6. Split algorithm is deterministic and fully specified

**Severity: INFO**

The six-step algorithm (partition by type, chunk modals by 5, chunk
selects by 5, concatenate) is specified with enough precision to
implement without ambiguity. The worked example matches the actual
Dark Nemesis form: 5 modal-compatible questions in one modal step,
2 select questions in one follow-up step. The algorithm does not depend
on runtime state, user input, or Discord API responses. It computes
once at load time and produces an immutable plan.

### 7. No test surface specified

**Severity: LOW**

The proposal is design-only and does not define test expectations. This
is acceptable at the proposal stage, but the validation rule density
(~40 rules) means implementation should include comprehensive test
coverage, particularly for boundary conditions (empty chapters list,
exactly 5 modal questions, exactly 25 select options, slug regex edge
cases). This is a normal implementation concern, not a scope risk.
