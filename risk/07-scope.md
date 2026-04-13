# Scope Risk Assessment: Roles Command

## Risk Level: LOW

## Findings

1. **Proposal matches needs exactly** (no issue)
   The 13 serialized fields in the proposal are a 1:1 match with the
   required fields listed in `research/07-roles-command-needs.md`. No
   fields were added or dropped between the needs synthesis and the
   proposal.

2. **No scope creep detected** (no issue)
   The proposal adds one subcommand, one handler, one registration
   entry, and one parser entry. It introduces no new utilities, no new
   flags, no new serialization helpers beyond what the existing pattern
   already provides (`iso_or_none` is reused). The handler shape
   (`async def fetch_roles(guild, args) -> dict`) is identical to every
   other command in the file.

3. **Anti-scope is well-defined** (no issue)
   The anti-scope section explicitly lists 11 exclusions covering
   member-dependent data, display/icon fields, tag objects, permission
   expansion, filtering/sorting flags, write operations, and
   backwards-compatibility shims. Each exclusion maps to a concrete
   feature that could plausibly have crept in. The tradeoffs section
   acknowledges the cost of four of these exclusions, which shows they
   were deliberate cuts rather than oversights.

4. **No dependency on future work** (no issue)
   The command is a self-contained read-only metadata export. It does
   not introduce any schema versioning, feature flags, or extension
   points that would create obligations for later proposals. The
   anti-scope items (`display_icon`, `tags`, permission expansion,
   sort/filter flags) are framed as potential future additions, not
   promises.

5. **Registration matches existing pattern** (no issue)
   The proposal registers in both `command_specs()` and
   `build_parser()`, consistent with how all six existing commands are
   wired. The parser entry is a no-argument subparser, matching the
   `overview`, `bots`, `channels`, and `integrations` commands. No new
   dispatch machinery is introduced.

## Recommendation

Accept. The proposal is a minimal, pattern-consistent addition with no
scope creep, no missing requirements, clear anti-scope, and no
obligations for future work.
