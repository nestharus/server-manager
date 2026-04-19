# Engineering Roadmap

## Technical Landscape Summary

The codebase still has one real canonical analogue: the chapter API in `services/api/` proves the intended layered path of `contracts`, `repositories`, `services`, and `api`, along with header-based optimistic locking and append-only activity records. That surface remains in-memory only, and the strongest current contract is still the activity-model test suite. Phase 0 therefore has to turn the current proof point into durable shared substrate before later slices can rely on it.

`services/discord/` is still a runtime shell rather than a feature daemon. Startup, settings, and bot wiring exist, but `commands/`, `handlers/`, and `tasks/` are placeholders. Most workflow behavior still lives in preserved draft-state code under `daemon/` and `forms/`, which is useful as hookpoint material but not as approved implementation surface.

There is still no migration layer, no durable repository implementation, and no completed workload substrate. The roadmap therefore keeps the hosting target framed as "as configured in `infra/`": the OpenTofu assets in-repo are the current baseline, and formalizing that hosting decision in `DECISIONS.md` remains a Phase 0 completion requirement.

## Foundation Phase

### Phase 0: Foundations

**Phase 0 aggregate:** XL (leans XL; this is still mostly greenfield substrate work, and the biggest uncertainty sits in scheduler, deployment, and permission-intent foundations rather than in any single CRUD surface)

Phase 0 establishes the operational substrate every subsequent phase builds on. The specific shape of each foundation item is determined by its implementation proposal. This roadmap commits to the capabilities Phase 0 delivers, not the detailed designs.

### Phase 0 delivers

- Persistence substrate with migrations
- Single write-path mutation primitive
- Audit and notification event contract
- Authority grant foundation
- Permission intent foundation
- Chapter role and roster entry foundation
- Policy version framework
- Scheduler
- Discord interaction framework
- Graceful degradation mechanics
- Data portability as a schema design property
- Shared test harness
- Deployable service substrate aligned to `infra/`

### Phase 0 foundation estimates

#### Persistence substrate with migrations

- **Rough magnitude:** L-XL (leans L; the data model is mostly greenfield, but there is no Alembic layer, no durable repository implementation, and the repo is not yet a clean installable service workspace)
- **Prototyping needed:** no (the uncertainty is integration breadth, not whether migrations and durable repositories are possible)

#### Single write-path mutation primitive

- **Rough magnitude:** M-L (leans M; the chapter service already demonstrates the action-plus-state-change pattern, but Phase 0 has to generalize it beyond one in-memory aggregate)
- **Prototyping needed:** no (there is a concrete analogue in `services/api/app/services/chapters.py`)

#### Audit and notification event contract

- **Rough magnitude:** M-L (leans M; audit primitives already exist, but notification grouping and event-shape discipline still need a shared contract)
- **Prototyping needed:** no (the main work is system design and wiring, not proving an unknown external behavior)

#### Authority grant foundation

- **Rough magnitude:** L (new cross-cutting governance model with no direct code analogue, but the core work is still durable schema plus service-layer enforcement rather than new external technology)
- **Prototyping needed:** conditional (only if scope resolution across global and chapter authority cannot be made deterministic from the proposal alone)

#### Permission intent foundation

- **Rough magnitude:** L-XL (leans L; the desired-vs-actual posture is conceptually clear, but the codebase has no permission-intent or reconciliation engine today)
- **Prototyping needed:** yes (Discord permission snapshot and reconciliation behavior is central and still novel in this codebase)

#### Chapter role and roster entry foundation

- **Rough magnitude:** M-L (leans M; this extends the existing chapter aggregate shape into roster state, but still needs new schema and durable role linkage)
- **Prototyping needed:** no (the uncertainty is normal lifecycle modeling, not a high-risk external API unknown)

#### Policy version framework

- **Rough magnitude:** M-L (leans M; header-based optimistic locking and diff generation already exist, but Phase 0 must lift them into a reusable policy/version chain)
- **Prototyping needed:** no (the chapter `ETag` analogue is already strong enough to skip a separate spike)

#### Scheduler

- **Rough magnitude:** L-XL (leans L; the roadmap needs deferred effects, retries, expiry, and recovery validation, and no task substrate exists in `services/discord/app/tasks/`)
- **Prototyping needed:** yes (the proposal must choose a scheduler shape before later time-based slices can estimate cleanly)

#### Discord interaction framework

- **Rough magnitude:** M-L (leans M; process startup and bot wiring exist, but every real command, handler, and API client path is still missing)
- **Prototyping needed:** no (the shell and preserved draft daemon give enough platform-specific precedent)

#### Graceful degradation mechanics

- **Rough magnitude:** M-L (leans M; the concept is straightforward, but the repo has no shared deferred-effect or retry/recovery path yet)
- **Prototyping needed:** conditional (only if the chosen retry/deferred-effects model cannot be validated from Phase 0 scheduler design alone)

#### Data portability as a schema design property

- **Rough magnitude:** S-M (leans S; this is mostly a constraint Phase 0 must enforce while defining canonical aggregates rather than a subsystem of its own)
- **Prototyping needed:** no (schema discipline and export-friendly identifiers do not need a separate spike)

#### Shared test harness

- **Rough magnitude:** M (the existing tests are split across roots, the monorepo is not bootstrapped cleanly, and baseline pytest currently fails before feature-level assertions run)
- **Prototyping needed:** no (the work is straightforward infrastructure cleanup)

#### Deployable service substrate aligned to `infra/`

- **Rough magnitude:** L-XL (leans L; infra and GitOps topology exist, but there are no workload manifests, no image/build pipeline, and hosting is not fully locked in `DECISIONS.md`)
- **Prototyping needed:** conditional (only if the final hosting decision or placeholder Flux/source wiring diverges materially from the current `infra/` baseline)

### Phase 0 acceptance criteria

- Hosting decision is formalized in `DECISIONS.md`
- Scheduler technology is selected by the Phase 0 proposal
- A single write-path primitive such as `mutate_entity()` is established for authoritative mutations
- The audit action and target registry pattern is selected
- Correlation and causation context propagation works at the request boundary
- Shared test harness is functional, including monorepo install and fixture support
- Deployable service substrate is operational against the `infra/` baseline
- Secret management is operational
- Authority grant, permission intent, policy version, chapter role, and roster entry foundations exist for downstream slices to consume
- Discord interaction framework can register commands, route handlers, and call the API surface
- Graceful degradation mechanics are selected for deferred effects, retries, and recovery validation
- Data portability is recorded as a schema property for Phase 0 aggregates

Each criterion is resolved by a dedicated AGENTS.md pipeline pass during Phase 0. This roadmap does not specify the resolution.

## Phase-Level Dependencies

- Phase 0 must complete before any Phase 1 slice begins.
- Phase 1 must complete before Phase 2 begins.
- Phase 2 must complete before Phase 3 begins.
- Phase 3 must complete before Phase 4 begins.
- Within each phase, slice ordering is not load-bearing at roadmap time. The AGENTS.md implementation pipeline determines concrete sequencing and worktree parallelization from the codebase state that exists when the phase begins.

## Phase Assignments

### Phase 1: Governance Foundation

Phase 1 delivers the governance substrate the operational workflows inherit later: trust, authority, audit, and policy safety. At the phase level, what exists is the chapter API proof point plus draft Discord runtime shell; what is new is durable governance infrastructure; what remains draft-state is the preserved pre-research daemon and form code. Phase 1 cannot begin until Phase 0 is complete. Within the phase, slice ordering is not load-bearing at roadmap time; the AGENTS.md implementation pipeline determines concrete parallelization from the codebase state that exists when work starts.

**Phase 1 aggregate:** XL (leans low-XL; the slices are conceptually bounded, but authority and policy mistakes would force rework across every later phase)

**Phase-specific risk posture:** Medium overall. The strategic risk is substrate quality rather than feature breadth: incomplete Phase 0 foundations would leak directly into Phase 1, and authority or policy mistakes would affect every later mutation surface.

**Slices in this phase:** VS-001, VS-002, VS-003, VS-004.

#### VS-001: Member onboarding with initial trust assessment

- **Capability delivered:** Members enter the system with an inspectable initial trust assessment derived from platform signals so officers begin from a shared trust baseline instead of memory and role presence.
- **Strategic risk:** Medium. The trust model becomes part of later governance decisions, so errors in signal capture or deterministic trust computation would propagate broadly.
- **Rough magnitude:** M-L (leans M; the trust domain is new, but the work is mostly greenfield schema plus deterministic computation on top of existing audit and API patterns)
- **Prototyping needed:** no (Discord/platform signal capture is understood enough; the uncertainty is implementation breadth, not feasibility)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 1 begins.

#### VS-002: Scoped authority with enforcement

- **Capability delivered:** Authority grants become explicitly scoped and automatically enforced so operational power no longer depends on broad Discord role hierarchy alone.
- **Strategic risk:** High. This is a cross-cutting control surface for all later mutations, so enforcement mistakes carry system-wide blast radius.
- **Rough magnitude:** L (cross-cutting governance surface with no direct implementation analogue; every later mutation path depends on the same scope-resolution rules)
- **Prototyping needed:** conditional (only if the chosen grant-resolution model cannot be proven against global-plus-chapter scope cases without a spike)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 1 begins.

#### VS-003: Audit trail with causal correlation

- **Capability delivered:** Decisions and state changes become durably queryable with causal linkage so operators can reconstruct what happened across workflows after Discord's native history window expires.
- **Strategic risk:** Medium. The risk is consistency across subsystems: if audit discipline is partial, later workflows lose the shared causal chain the roadmap depends on.
- **Rough magnitude:** M (the activity-model proof point is already the strongest contract in the repo; the remaining work is durable storage and broader adoption)
- **Prototyping needed:** no (the audit model already exists and the unknowns are not exploratory)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 1 begins.

#### VS-004: Policy versioning with configuration safety

- **Capability delivered:** Live configuration changes move to preview-confirm versioned policy updates so operators can evolve rules without silently corrupting in-flight work.
- **Strategic risk:** Medium. Activation, pinning, and stale-preview errors would undermine governance safety across every policy-backed subsystem.
- **Rough magnitude:** M-L (leans M; there is a clear `ETag`/`If-Match` analogue, but it still has to become a generic subsystem rather than chapter-only proof code)
- **Prototyping needed:** no (the concurrency mechanism is already demonstrated in the chapter API)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 1 begins.

### Phase 2: Core Operational Workflows

Phase 2 delivers the operator-facing workflows communities actively need to switch onto the platform: chapters, applications, tickets, permissions, notifications, advanced trust, and cross-subsystem views. At the phase level, what exists is limited chapter proof-point code plus preserved draft workflow artifacts; what is new is the actual operational system; what remains draft-state is any preserved SQLite-era implementation material used only as hookpoint input. Phase 2 depends on Phase 1 completion. Within the phase, slice ordering is not load-bearing at roadmap time; the AGENTS.md implementation pipeline determines concrete parallelization per worktree from the live codebase state when the phase starts.

**Phase 2 aggregate:** XL (leans high-XL; this is the widest feature phase, and the largest uncertainty sits in permission control-plane work plus live Discord chapter provisioning)

**Phase-specific risk posture:** Medium to high. VS-005 is the operational bottleneck for the chapter track, and VS-008 is the declared-intent control-plane bottleneck for permissions. The rest of the phase can move independently once the phase starts, but those two slices carry the main strategic schedule risk.

**Slices in this phase:** VS-005, VS-006, VS-007, VS-008, VS-009, VS-010, VS-015.

#### VS-005: Chapter provisioning from templates

- **Capability delivered:** New chapters can be proposed, approved, and provisioned from templates instead of being assembled manually across Discord resources and spreadsheets.
- **Strategic risk:** High. This slice crosses into live Discord resource creation and becomes a bottleneck for the later chapter lifecycle track.
- **Rough magnitude:** L-XL (leans L; there is a chapter API analogue, but actual provisioning adds greenfield durable schema, permission intent, and Discord resource orchestration)
- **Prototyping needed:** yes (template-driven Discord provisioning and rollback behavior are core unknowns with real rate-limit and resource-cap edge cases)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-006: Structured application intake with reviewer ownership

- **Capability delivered:** Applications move through a structured queue with explicit reviewer ownership and recorded decisions instead of informal shared review.
- **Strategic risk:** Medium. Reviewer-collision mistakes or an incomplete migration away from preserved draft logic would directly affect intake credibility.
- **Rough magnitude:** M-L (leans M; `daemon/applications.py`, `daemon/config.py`, and form YAML already cover much of the interaction shape even though the canonical persistence path is still missing)
- **Prototyping needed:** no (the draft daemon provides enough concrete hookpoints to skip a feasibility spike)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-007: Ticket creation and case lifecycle

- **Capability delivered:** Cases move through durable ticket workflows with category-specific lifecycle control instead of ad hoc DM and thread handling.
- **Strategic risk:** Medium. The main risk is getting private-thread and category-state behavior right without overfitting Discord constraints.
- **Rough magnitude:** M-L (leans M; there is shallow legacy ticket and claim material, but canonical category/state models and new handlers still need to be built)
- **Prototyping needed:** no (private-thread behavior already has a tested helper, and the remaining work is standard workflow construction)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-008: Permission intent and drift detection

- **Capability delivered:** Operators can declare intended permission state, detect drift against Discord reality, and reconcile differences from an explicit control plane.
- **Strategic risk:** High. This slice introduces the most novel operational model in the roadmap's core workflow phase and becomes the main permission substrate for later slices.
- **Rough magnitude:** XL (novel pattern in this codebase with no preserved implementation analogue; it needs new intent tables, drift diffing, Discord readers, and a reconciliation surface)
- **Prototyping needed:** yes (Discord permission snapshot and diff behavior is the main technical unknown and decides how much machinery the full slice needs)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-009: Configurable operator notifications

- **Capability delivered:** Notifications become configurable and causally grouped so officers are informed without turning alert volume into a separate burnout source.
- **Strategic risk:** Medium. The risk is fan-out and event-grouping correctness once multiple workflows start emitting operational activity.
- **Rough magnitude:** M-L (leans M; this depends on shared event discipline and background dispatch, but it does not introduce a wholly new domain model)
- **Prototyping needed:** conditional (only if grouped fan-out semantics or Discord delivery throttling prove harder than the event contract suggests)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-010: Advanced trust management

- **Capability delivered:** Trust moves beyond initial onboarding into officer-managed signals, overrides, and recomputation so trust remains an operational system rather than a one-time intake score.
- **Strategic risk:** Medium. The trust domain now spans policy changes, endorsements, and recomputation, so determinism and operator control must stay aligned.
- **Rough magnitude:** M-L (leans M; once VS-001 exists this is mostly state-machine and policy-extension work on the same trust substrate)
- **Prototyping needed:** no (the high-uncertainty question is initial trust modeling, not the existence of later overrides and recomputation)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

#### VS-015: Cross-subsystem operational views

- **Capability delivered:** Operators gain shared read views across workflows so they can see what is happening across applications, tickets, permissions, and governance without reconstructing context manually.
- **Strategic risk:** Medium. Projection freshness and cross-workflow correlation matter because these views depend on the event discipline established earlier.
- **Rough magnitude:** M-L (leans M; read projections are greenfield, but they can build on the audit/event substrate instead of inventing a new mutation model)
- **Prototyping needed:** no (this is projection and query shaping, not an unknown platform problem)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 2 begins.

### Phase 3: Operational Depth

Phase 3 deepens the core workflows into the package communities actually pay to consolidate: roster lifecycle, interviews and waitlists, ticket SLA enforcement, and temporary permission expiration. At the phase level, what exists is only the base workflow substrate from Phases 1 and 2; what is new is lifecycle depth and time-based enforcement; what remains draft-state is any pre-existing draft workflow behavior that still needs replacement rather than direct reuse. Phase 3 depends on Phase 2 completion. Within the phase, slice ordering is not load-bearing at roadmap time; the AGENTS.md implementation pipeline determines concrete parallelization from the concrete codebase state at execution time.

**Phase 3 aggregate:** XL (leans low-XL; most slices are extensions of earlier contracts, but timed enforcement and live role expiry keep the phase from being a trivial follow-on)

**Phase-specific risk posture:** Medium overall. The phase is strategically less novel than Phase 2, but it depends on earlier workflow contracts staying stable. VS-013 carries the main timing risk because time-based enforcement compounds scheduler and notification dependencies, while permission lifecycle work continues to depend on the declared-intent model established earlier.

**Slices in this phase:** VS-011, VS-012, VS-013, VS-014.

#### VS-011: Roster management with role lifecycle

- **Capability delivered:** Officers gain full roster lifecycle management, including role and status transitions, instead of treating membership state as spreadsheet metadata around Discord roles.
- **Strategic risk:** Medium. Roster state touches chapters, authority, and Discord role synchronization, so lifecycle mistakes would ripple across governance and compliance work later.
- **Rough magnitude:** L (clear chapter and audit analogues exist, but live role synchronization and lifecycle integrity make this larger than a basic CRUD slice)
- **Prototyping needed:** conditional (only if Discord role-sync edge cases or chapter/authority coupling are not sufficiently resolved by the Phase 2 chapter substrate)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 3 begins.

#### VS-012: Application interview and waitlist handling

- **Capability delivered:** The application system gains interview and waitlist handling so applicants can move through richer intake paths without falling back to untracked side channels.
- **Strategic risk:** Medium. Additional state transitions and notification touchpoints make this an extension risk rather than a foundational one.
- **Rough magnitude:** M (extends the Phase 2 application state machine with richer transitions rather than creating a new subsystem)
- **Prototyping needed:** no (the behavior is a direct extension of the application workflow and existing Discord thread affordances)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 3 begins.

#### VS-013: SLA enforcement for tickets

- **Capability delivered:** Ticket workflows gain time-based accountability with graduated escalation so sensitive or operationally important cases do not age silently.
- **Strategic risk:** High. This slice concentrates scheduler reliability, notification routing, and category-specific escalation semantics into one operational control loop.
- **Rough magnitude:** L (depends on scheduler, notification routing, and ticket-category semantics all holding together; the work is not novel like OCR, but it is coordination-heavy)
- **Prototyping needed:** conditional (only if scheduler/retry behavior for escalations remains ambiguous after Phase 0 chooses the workload substrate)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 3 begins.

#### VS-014: Temporary permission management

- **Capability delivered:** Temporary permission grants become explicit, expiring operational state instead of quietly hardening into permanent baseline access.
- **Strategic risk:** Medium. The risk is lifecycle correctness on top of the Phase 2 permission-intent model: expirations must be timely and must not create duplicate or stale drift.
- **Rough magnitude:** M-L (leans M; this extends the permission-intent model with expiry and recovery paths instead of inventing a second permission subsystem)
- **Prototyping needed:** no (if VS-008 lands cleanly, this is lifecycle extension work rather than exploratory platform work)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 3 begins.

### Phase 4: Operational Maturity

Phase 4 closes the roadmap with compliance evaluation, chapter governance lifecycle, and leadership succession. At the phase level, what exists is still only the shared governance and workflow substrate from earlier phases; what is new is mature lifecycle control over evidence, chapters, and leadership continuity; what remains draft-state is effectively none of the final capability itself. Phase 4 depends on Phase 3 completion. Within the phase, the AGENTS.md pipeline still determines the concrete implementation sequence, but the strategic risk posture is more serial than earlier phases because later governance and succession work depend on the maturity of compliance and chapter-state handling.

**Phase 4 aggregate:** XL (leans XL; VS-016 dominates the uncertainty and the rest of the phase inherits its evidence and consequence quality)

**Phase-specific risk posture:** High. VS-016 concentrates external dependency and evidence-processing uncertainty, and the phase's downstream slices depend on the quality of the operational outcomes it introduces.

**Slices in this phase:** VS-016, VS-017, VS-018.

#### VS-016: Compliance rule evaluation with evidence

- **Capability delivered:** Compliance becomes a scheduled, evidence-backed workflow so officers stop doing repetitive rule evaluation and enforcement by hand.
- **Strategic risk:** High. This slice concentrates external provider dependency, evidence-processing uncertainty, and cross-subsystem consequence routing.
- **Rough magnitude:** XL (Google Cloud Vision primary plus Gemini fallback is locked, and the repo has no OCR adapters, evidence pipeline, or compliance models today)
- **Prototyping needed:** yes (OCR accuracy, confidence thresholds, and fallback rates are the defining uncertainty for the slice)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 4 begins.

#### VS-017: Chapter governance lifecycle

- **Capability delivered:** Chapters gain formal governance states such as probation and archival so sub-community health can be managed through explicit lifecycle transitions rather than informal cleanup.
- **Strategic risk:** Medium. The risk is cross-subsystem pending-work handling and safe chapter-state transitions once compliance and roster consequences are in play.
- **Rough magnitude:** M-L (leans M; it extends chapter lifecycle and pending-work handling on top of chapter, roster, and compliance substrates rather than inventing a new external integration)
- **Prototyping needed:** no (the uncertainty is policy and workflow coupling, not platform feasibility)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 4 begins.

#### VS-018: Leadership succession with context transfer

- **Capability delivered:** Leadership handoffs preserve authority continuity and pending operational context instead of forcing each transition to reconstruct state from memory.
- **Strategic risk:** Medium. Succession spans authority, chapters, roster state, and open work, so transfer mistakes can create governance discontinuity at exactly the wrong time.
- **Rough magnitude:** M-L (leans M; it is cross-subsystem, but it mostly composes already-built authority, roster, and operational-view capabilities)
- **Prototyping needed:** no (there is no major external unknown once the underlying governance surfaces exist)
- **Implementation pipeline:** This slice runs through AGENTS.md research -> proposal -> risk -> hookpoints -> test/code when Phase 4 begins.

## Executive Pushback Summary

No engineering pushback changes the executive phase assignments. All 18 value slices remain in their approved phases.

The strategic-only change is in the level of commitment. The roadmap now commits to phase order, slice scope, phase-level dependencies, phase-level risk posture, rough magnitude bands, and prototyping flags. It does not commit to precise schedules, ownership splits, contract signatures, or staffing assumptions. Within each phase, slice ordering is not load-bearing at roadmap time; the AGENTS.md implementation pipeline determines concrete sequencing and worktree parallelization from the actual codebase state when that phase begins.

## Critical Path Summary

The strategic critical path remains:

`Phase 0 foundations -> Phase 1 governance foundation -> Phase 2 operational workflows -> Phase 3 operational depth -> Phase 4 operational maturity`

Within that sequence, the narrowest strategic chain still runs through the slices that define shared control surfaces or bottleneck later work: `VS-002`, `VS-008`, and `VS-016`, followed by the chapter-governance and succession finish in `VS-017` and `VS-018`. That is the roadmap's main sequencing reality. The implementation pipeline determines the exact per-slice execution order and concurrency when those phases are actually built.
