# Engineering Roadmap Revision Report Cycle 6

## Scope

This revision is feasibility-only. It keeps all 18 value slices, preserves their phase assignments, and does not add feature scope beyond the approved proposal.

## Revisions Applied

| Finding | Revision | Result |
|---|---|---|
| F-1. Hosting decision not locked in `DECISIONS.md` | Added explicit Phase 0 acceptance criteria, including: `DECISIONS.md` entry formalizing the hosting decision (Vultr VKE per the `infra/` artifacts) is committed before Phase 0 completion. | The hosting formalization is now a tracked Phase 0 deliverable instead of an implicit prerequisite. |
| F-2. Critical path has little slack | Added a `Buffer and Slack` section. It states that the critical path has no built-in slack and defines three mitigations: prioritized Phase 0 primitive delivery, 20% buffer on each Phase 0 L item, and automatic downstream re-scheduling when primitives slip. | The roadmap now acknowledges the schedule exposure directly and turns slack handling into explicit policy. |
| F-3. VS-009 effort too optimistic | Upgraded `VS-009: Configurable operator notifications` from M to L and revised the effort reasoning to reflect notification rules, causal grouping, delivery adapters, and scheduler and Discord coupling. | The estimate now matches the slice's actual ownership. |
| F-4. `PolicyVersion` activation and pinning buried in a single M row | Split the old Phase 0 policy row into three lines: locking cleanup, `PolicyVersion` framework, and `PolicyVersion` activation and pinning service. | The activation and pinning work is now explicit and separately tracked. |
| F-5. Test harness M absorbs too much | Upgraded the Phase 0 API and Discord test harness item from M to L. | The estimate now reflects monorepo install repair, stale-test reconciliation, and new fixture and interaction utility work. |
| F-6. Phase 4 serialization risk understated | Added explicit Phase 4 language in `VS-017` and in `Effort Summary` that Phase 4 is the highest-risk phase. Added the checkpoint: confirm VS-016 compliance evaluation is shipping before committing to Phase 4 timeline assumptions. | The roadmap now names the serial Phase 4 risk and adds a concrete gate before the second slice starts. |

## Mechanical Impact

- Phase 0 foundation breakdown changed from `5L + 7M` to `6L + 7M`.
- Phase 0 foundation item count changed from 12 to 13 because the `PolicyVersion` work is now split into distinct tracked items.
- Phase 2 serial effort changed from `2XL + 3L + 2M` to `2XL + 4L + M` because VS-009 is now L.
- Total serial effort changed from `4XL + 13L + 13M` to `4XL + 15L + 12M`.

## Guardrail Check

- All 18 value slices remain present.
- No slice moved across phases.
- No new operator-visible feature scope was added.
- Revisions are limited to feasibility controls, effort sizing, and explicit gating language.
