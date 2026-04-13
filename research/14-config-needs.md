# Synthesis: daemon/config.py Needs

Date: 2026-04-13

## Context

Research in `research/14-config.md` established:
- PyYAML 6.0.3 is available; `yaml.safe_load()` is the safe loading method
- `chapters.yaml` has format `chapters: []` (list of chapter entries)
- `forms/dark-nemesis.yaml` defines 7 questions with types: short, long, select, multi_select, number
- Discord modals support max 5 components; forms >5 fields need multi-step splitting
- The daemon design says config.py handles loading/validation, not runtime logic
- Python 3.12+ means dataclasses and `typing` are fully available

## Humility-Specific Needs

1. **Load chapters.yaml**: Parse the chapter registry. Currently empty (`chapters: []`). Must handle the empty case gracefully. Each chapter entry (once populated) will reference a form file path and chapter metadata.

2. **Load forms/<slug>.yaml**: For each chapter, load its form definition. Parse question types (short, long, select, multi_select, number), validate required fields, validate options for select/multi_select.

3. **Structured config objects**: Use dataclasses (not Pydantic — it's not a dependency) to represent:
   - Chapter config (slug, display_name, role IDs, channel IDs, form_path)
   - Form config (id, title, questions list)
   - Question config (id, type, label, required, max_length, options)

4. **Multi-step modal awareness**: The config loader should compute the modal split for forms with >5 fields. The Dark Nemesis form splits: modal#1 = [ign, hours, budget_launch, budget_monthly, experience] (5 text inputs), follow-up = [timezone select, daily_events multi-select]. This logic belongs in config since it's deterministic from the form definition.

5. **Validation at load time**: Catch errors early:
   - Missing/unreadable YAML files → clear error
   - Malformed YAML → clear error with file path
   - Unknown question types → error
   - Select/multi_select without options → error
   - Form with no questions → error

6. **Hot-reload friendly**: Functions that load from disk, not cached module-level globals. The daemon can call `load_config()` on startup and on `/reload`.

7. **No daemon runtime logic**: No Discord interactions, no database access, no slash command handling. Pure file I/O and validation.

## Gaps

None. The research covers all aspects needed for a proposal.
