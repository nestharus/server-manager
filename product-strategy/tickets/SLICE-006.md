# SLICE-006: API and Discord runtime plumbing

## Parent

**Initiative:** Phase 0 foundation slice
**Phase:** Phase 0

## What Changes for the Operator

The API and Discord services become bootable, health-checkable, and correlation-aware runtime surfaces. Later Discord-facing slices can register commands, dispatch handlers, and call the API without reworking startup or request context plumbing.

## Justification Chain

**Market signal:** Cross-cutting findings show the strongest competitors are platform-bound, so a clean Discord/API boundary is part of the differentiation rather than a hidden implementation detail.
**Problem axis:** §12 — Cross-workflow State and Operational Continuity
**Proposal mechanism:** proposal.md, Platform Boundary; Operational Workflows; Governance Mechanisms -> Audit Chain
**Philosophy principles:** Principle 8: Platform-Native Interaction, Principle 12: Graceful Degradation, Principle 15: Traceability as Outcome

## Technical Specification

**Schema objects:**
- InteractionEnvelope / InteractionHandler: single registry and dispatch contract for Discord interactions
- ApiTransportRequest / ApiTransportResponse: correlation-aware Discord->API request port
- ServiceHealthRead / ServiceReadinessRead / DiscordRuntimeRead: boot, liveness, and readiness surfaces

**API endpoints:**
- GET /api/v1/health -> ServiceHealthRead
- create_api_app(settings: ApiSettings) -> FastAPI
- GET /api/v1/ready -> ServiceReadinessRead
- run_discord_daemon(settings: DiscordSettings) -> DiscordRuntimeRead

**Discord interactions:**
- single registry-based command dispatch for all later Discord feature slices

**State transitions:**
- interaction received -> correlation-aware handler dispatch
- service boot -> live/ready or named blocking dependency

## Work Units

| Work Unit | Contract | Test Boundary | Code Boundary |
|---|---|---|---|
| WU-009C | Discord Interaction Registry And Dispatch Foundation | `services/discord/app/contracts/interactions.py` | services/discord/app/contracts/interactions.py, services/discord/app/core/bot.py, services/discord/app/commands/__init__.py, services/discord/app/handlers/__init__.py, services/discord/tests/test_interaction_framework.py |
| WU-009D | Discord API Transport Foundation | `services/discord/app/contracts/api_transport.py` | services/discord/app/contracts/api_transport.py, services/discord/app/infrastructure/api_client.py, services/discord/tests/test_api_transport.py |
| WU-010C | API Factory And Liveness Substrate | `services/api/app/contracts/runtime.py` | services/api/app/contracts/runtime.py, services/api/app/api/v1/endpoints/health.py, services/api/app/core/factory.py, infra/tests/test_api_runtime.py |
| WU-010D | API Readiness Surface | `services/api/app/contracts/runtime.py` | services/api/app/contracts/runtime.py, services/api/app/api/v1/endpoints/ready.py, infra/tests/test_api_readiness.py |
| WU-010E | Discord Runtime Entrypoint | `services/discord/app/contracts/runtime.py` | services/discord/app/contracts/runtime.py, services/discord/app/__main__.py, infra/tests/test_discord_runtime.py |

## Dependencies

**Upstream slices:** none
**Foundation dependencies:** SLICE-001, SLICE-002, SLICE-005
**Parallelizable with:** SLICE-003, SLICE-004

## Acceptance Criteria

- [ ] The API service boots against the checked-in infra baseline and exposes separate liveness and readiness surfaces.
- [ ] The Discord service boots against the checked-in infra baseline and names missing dependencies on startup failure.
- [ ] Discord-originated API calls preserve correlation_id and causation_id context through the transport layer.
- [ ] Later Discord feature slices add only commands/handlers and do not modify registry or transport foundations.

## Engineering Notes

**Effort:** Discord interaction framework -> M-L (leans M); Deployable service substrate aligned to `infra/` -> L-XL (leans L)
**Prototyping:** Discord interaction framework -> no; Deployable service substrate aligned to `infra/` -> conditional
**Risk:** Medium — later feature slices will fan out across this shell, so request context and startup contracts must be stable before workflow work begins.
**Existing code:** `services/discord/` already contains startup, settings, and bot wiring placeholders; this slice formalizes them into a reusable shell.
**Known challenges:** Keeping the platform boundary thin and correlation-aware while avoiding feature-specific helper sprawl in foundation code.
