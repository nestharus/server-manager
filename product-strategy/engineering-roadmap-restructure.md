# Engineering Roadmap Restructure

## Purpose

This restructure moves `engineering roadmap.md` back to a roadmap artifact instead of an implementation-plan surrogate. The previous revisions kept generating new MEDIUM findings because the document committed to details that cannot be resolved reliably before a slice enters the AGENTS.md implementation pipeline. The revised roadmap therefore keeps strategic commitments and removes spec-level commitments.

## What was retained

- All 18 value slices, unchanged
- All phase assignments, unchanged
- Technical Landscape Summary
- A restructured Phase 0 section centered on capabilities delivered and acceptance criteria
- Phase-level dependencies
- Phase-level risk posture
- One compressed strategic summary for each slice
- Executive Pushback Summary
- Critical Path Summary

## What was removed

- Per-slice T-shirt effort sizes and aggregate effort rollups
- Pairwise parallelization maps and slice-pair dependency claims
- Per-slice ownership splits such as which phase "owns" a table versus service boundary
- Contract-level commitments such as decorator signatures, service signatures, and endpoint shapes
- Buffer and slack percentages
- Per-slice "what exists / what is new / what is draft-state" analysis
- Effort Summary tables
- The old roadmap's implementation-plan framing around exact sequencing inside phases

## Why those items were removed

Those commitments belong to the per-slice implementation pipeline:

- Research resolves the actual problem shape at slice start
- Proposal resolves the design and scope against current codebase state
- Risk review validates whether the design is safe enough to implement
- Hookpoint research determines what existing code survives and what does not
- Test and code passes resolve contracts and ownership in executable form

When the roadmap commits to those details early, it freezes assumptions that are supposed to stay open until slice execution. That is what drove the repeated MEDIUM findings cycle.

## What changed in Phase 0

Phase 0 is now framed as an explicit substrate phase with two strategic sections:

- `Phase 0 delivers`, which names the shared capabilities later slices depend on
- `Phase 0 acceptance criteria`, which names what must be true before any Phase 1 slice can start

This keeps the roadmap honest about what Foundations must achieve while avoiding roadmap-time specification of scheduler choice, audit registry implementation, hosting mechanics, or mutation-path details. Those are now explicitly implementation-pipeline outputs.

## Result

`engineering roadmap.md` is now a strategic sequencing document. It preserves scope, phase order, and phase-level risk, while deferring implementation-level commitments to the AGENTS.md slice pipeline where they can be resolved against the real codebase at execution time.
