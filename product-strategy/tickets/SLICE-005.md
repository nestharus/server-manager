# SLICE-005: Test harness and runtime settings

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

Contributors and deployment operators gain stable API and Discord test fixtures plus environment/secret contracts that match the checked-in infra baseline. This lets later slices ship against one runtime contract instead of ad hoc bootstrap assumptions.

## Justification Chain

**Market signal:** Governance evidence highlights vendor-maturity risk and moving-target platform dependency, making inspectable runtime configuration and reproducible tests part of the product risk surface.
**Problem axis:** §11 — Platform Constraints and Moving-Target Risk
**Proposal mechanism:** proposal.md, Platform Boundary; Constraint Acknowledgments
**Philosophy principles:** Principle 4: Research Before Implementation, Principle 8: Platform-Native Interaction, Principle 12: Graceful Degradation

## Technical Specification

**Schema objects:**
- ApiTestHarnessRead / DiscordTestHarnessRead: fixture boundaries for API and Discord tests
- ApiSettings / DiscordSettings / SettingsSourceRead: runtime configuration and secret-source contracts

**API endpoints:**
- none

**Discord interactions:**
- test-only interaction fixtures through the Discord harness

**State transitions:**
- service boot with complete required secrets -> successful settings load; missing required secret -> fail-fast startup error

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-009A | API Test Harness Foundation | `services/api/app/contracts/testing.py` | services/api/app/contracts/testing.py, services/api/tests/conftest.py, services/api/tests/test_harness.py |
| WU-009B | Discord Test Harness Foundation | `services/discord/app/contracts/testing.py` | services/discord/app/contracts/testing.py, services/discord/tests/conftest.py, services/discord/tests/test_harness.py |
| WU-010A | API Service Settings Substrate | `services/api/app/contracts/runtime_settings.py` | services/api/app/contracts/runtime_settings.py, services/api/app/core/settings.py, services/api/tests/test_settings.py |
| WU-010B | Discord Service Settings Substrate | `services/discord/app/contracts/runtime_settings.py` | services/discord/app/contracts/runtime_settings.py, services/discord/app/core/settings.py, services/discord/tests/test_settings.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** none
**Parallelizable with:** SLICE-001

## Acceptance Criteria

- [ ] API tests run from the monorepo root with database and actor-context fixtures available.
- [ ] Discord tests boot the command registry without network access and stub API calls through one fixture boundary.
- [ ] Both services fail fast when required secrets are missing.
- [ ] Settings contracts map to the secret and environment variable names already referenced by checked-in infra manifests.

## Engineering Notes

**Effort:** Shared test harness -> M
**Prototyping:** Shared test harness -> no
**Risk:** Medium — without this substrate, later slices will encode runtime assumptions into feature code and lose reproducible contract-level verification.
**Existing code:** `services/discord/` already has a runtime shell for settings and bot startup that can be formalized instead of reinvented.
**Known challenges:** Keeping test fixtures contract-only and aligned with the infra baseline instead of leaking implementation internals into tests.
