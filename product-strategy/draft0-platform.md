# Draft 0 Platform Proposal

Status: evolving draft built from `.tmp/partitions/0000.md` upward.

## Current Final Direction

The durable platform direction emerges only after the research-first reset. The opening local CLI and the first Railway+SQLite daemon sketch are both provisional drafts, not final platform commitments.

By the middle-late session, the direction is no longer "one cluster provisioned directly by Terraform." It evolves through a Hetzner-first phase, then a practical pivot to Vultr VKE, and then a deeper architectural correction when `base-application` shows the intended pattern: OpenTofu bootstraps a platform cluster, Flux manages desired state from Git, and Crossplane provisions downstream application clusters from inside the platform.

## Hosting And Environment Evolution

- Initial environment was entirely local:
  - local working directory
  - local virtualenv
  - local `.env` with Discord bot token and guild ID
- No hosting/provider choice yet.
- The local Python environment standardizes quickly on `uv` with `pyproject.toml` and `uv.lock`.
- The first concrete hosting proposal later in the prototype phase is Railway with a long-running bot process and persistent storage.
- At reset time, the user explicitly rejects local-first optimization and says the system must run in the cloud 24/7.
- The first formal proposal then picks Railway + Supabase as the default deployment posture, before later platform decisions pull the architecture into a fuller monorepo/services split.
- Immediately after the first implemented API slice, Supabase is explicitly questioned and the hosting/database conversation pivots again.
- In the first robust platform proposal, the stack swings toward Hetzner + kube-hetzner for cost reasons.
- During implementation, Hetzner stops looking practical:
  - account limits show `0/5` servers and `0/8` vCPU available
  - the user explicitly says Hetzner "seems like a pain"
  - Contabo is investigated but treated as too risky for production Kubernetes
- The practical provider direction then pivots to Vultr VKE because:
  - managed Kubernetes reduces bootstrap burden
  - the user already has Vultr credentials
  - Vultr also covers adjacent needs like object storage and managed services better than the Hetzner path
- Environment model also changes materially in this period:
  - `production` stays persistent
  - `dev` is added as a persistent application-development and E2E environment
  - `staging` is redefined as on-demand release-candidate benchmarking infrastructure rather than always-on QA
  - separate ephemeral platform-test environments remain useful for infrastructure validation

## Infrastructure Architecture

- Earliest infrastructure assumption is minimal local tooling, not cloud deployment.
- Discord access is through a bot token; no OAuth login flow or redirect URI is needed for this operating mode.
- No database, no message queue, and no external hosting surface appear in the early bootstrap.
- Operational constraint discovered during live inspection: the Discord-side runtime has to tolerate large-guild behavior and avoid heavy default gateway operations like full member chunking.
- Another early constraint emerges: vendor dashboards are outside the assistant's control surface, so any architecture that depends on them inherently breaks the project's orchestration model.
- The first serious self-host architecture proposal is still mono-process: one Discord daemon owning workflow logic and state.
- After the reset, platform architecture is intentionally deferred until research has earned it.
- OCR research later adds another platform dimension: screenshot ingestion and extraction become part of the eventual runtime, not just text/chat workflow automation.
- The first formal proposal's concrete platform stack was:
  - Railway for compute
  - Supabase Postgres as system of record
  - Google Cloud Vision primary + Gemini fallback for OCR
  - `discord_cli.py` preserved as sibling inspection tool
- That stack is later adjusted as new reference-repo decisions arrive.
- The first risk-cleared foundation implementation after the legacy-doc phase still assumes a flatter model:
  - OpenTofu creates the Kubernetes substrate
  - Flux manages cluster configuration
  - Helm/Kustomize deploy the first shared services
- Later user correction and reference-repo discovery split this into three distinct layers:
  - OpenTofu bootstraps foundational cloud resources from outside the cluster
  - Flux + Helm + Kustomize reconcile desired state on clusters from Git
  - Crossplane provisions additional cloud/application resources from inside the platform cluster
- `base-application` introduces the intended two-tier cluster model:
  - one platform cluster hosts shared platform services
  - application clusters are created declaratively per environment
  - Flux watches Git and Crossplane materializes cluster resources
- This discovery is load-bearing because it invalidates the simpler "single VKE cluster with everything in namespaces" interpretation of Phase 1.

## Database Direction And Pivots

- First bootstrap-era persistence idea for a custom applications subsystem:
  - SQLite file, or
  - Discord-channel-backed submission log
- This is not a settled decision; later workflow reset explicitly rejects local-first/SQLite assumptions being baked in too early.
- During the daemon prototype, SQLite becomes the concrete implementation choice for chapters, submissions, tickets, and blacklist state.
- Partition `0112` is the decisive rejection of SQLite as the durable basis for the cloud system.
- Later OCR research narrows ingestion choices to classical OCR, vision-LLM, or mixed designs, with spend low enough that architecture and reliability dominate the choice.
- Proposal revisions also show platform tradeoff churn:
  - initial hardening added DB-enforced append-only history
  - scope review pushed back on over-engineering for Humility's actual size
  - OCR engine choice remains intentionally deferrable because schema/runtime design stays backend-agnostic
- In the next hosting pivot, the database conversation moves:
  - from Supabase Postgres
  - to Railway Postgres as the simpler same-vendor option
  - then beyond Railway toward Vultr/Hetzner/self-hosted Postgres choices
- The late database-stack research reaches a much more concrete recommendation:
  - Atlas for declarative schema management and migrations
  - SQLAlchemy Core for the default async repository layer
  - `asyncpg` for exceptional SQL-heavy paths
  - `testcontainers-python` + template databases for E2E isolation
  - SQL base seeds plus SQL scenario overlays, with generated fake data only where needed
- Important eliminations and corrections in that research:
  - Prisma Client Python is treated as non-viable because it is archived/unmaintained
  - full ORM usage is avoided; query builder plus explicit SQL is preferred
- Another late database/platform idea becomes load-bearing:
  - treat part of the database as a versioned release artifact
  - production images carry schema plus release/reference data
  - mutable user/state data lives in volumes and must still be migrated in place
  - E2E can use specialized seeded DB images for scenario testing

## GitOps And Provisioning

- Proposal-stage deployment thinking includes:
  - Git-based source of truth for forms and code
  - Alembic-managed schema migrations
  - staging and production split
  - later chapter provisioning through explicit planned steps rather than ad hoc Discord clicks
- By partition `0240`, a new platform decision packet exists in `.tmp/d8-platform-decisions.md` that points toward:
  - Python, not Rust
  - FastAPI API service
  - discord.py daemon
  - TanStack web frontend
  - monorepo structure adapted from reference repos
- The user also clarifies that "scope" should be addressed by phased PRs and validation, not by feature cuts.
- Later platform work makes the GitOps boundary much more concrete:
  - OpenTofu is for external bootstrap only
  - Flux is the desired-state engine
  - Helm/Kustomize carry in-cluster service configuration
  - Crossplane is the in-cluster infrastructure provisioning layer
- This means the platform is converging on Git-managed environment declarations that can create or destroy downstream clusters, not just deploy workloads into one preexisting cluster.
- Release-management thinking later gets folded into this same control model:
  - environments and release channels are treated as closely related control surfaces
  - promotion should be explicit and serialized
  - downstream environments should watch the correct release channel rather than being updated ad hoc

## Monitoring And Operations

- Monitoring is initially unspecified, but becomes concrete during the Phase 1 foundation work.
- Direction that emerges in the mid-session platform build:
  - Prometheus / Alertmanager / Grafana baseline
  - monitoring deployed as shared platform capability rather than ad hoc per service
  - later AIOps layer via StackStorm
  - `droid` as an internal AI service
  - z.ai default with MiniMax fallback for internal automation use cases

## Base-Application And Reference Patterns

- `ai-workflow` becomes the primary backend structure reference:
  - layered split across API, contracts, core, infrastructure, repositories, services
- `java-interview-setup` contributes selected patterns:
  - optimistic locking
  - auditing
  - testing ideas
- `ui-designer` contributes monorepo/UI practices:
  - Bun + Turborepo workspace structure
  - frontend/testing conventions
  - TanStack-oriented frontend direction (with explicit user note that this project should not use Next.js)
- `ai-workflow` also contributes CI/review/tooling expectations:
  - heavy local linting pipeline
  - CodeRabbit configuration and review loop
  - testing pipeline and process docs
- `base-application` later becomes the critical infrastructure reference:
  - platform cluster bootstrap via Terraform/OpenTofu
  - Flux-managed GitOps structure
  - Crossplane XRDs/compositions for provisioning downstream application clusters
  - service deployment through Helm/Kustomize
  - clear separation between platform services and application workloads

## What Was Actually Deployed Vs Planned

- In the first batch, only local bootstrap was planned and executed.
- No cloud infrastructure, database, or deployment surface had been chosen yet.
- A persistent daemon is first proposed during bootstrap, but it is only a sketch at this point and not a real deployment decision.
- tickets.bot v2 was explored as a possible external replacement for ticketsbot.net, but no assistant-manageable infrastructure path emerged from that exploration.
- A prototype daemon was actually run locally and did connect/sync commands against the live guild.
- Railway deployment config was planned, but not yet a real deployed environment.
- After the reset, those prototype artifacts are kept only as pre-research drafts pending hookpoint analysis.
- A private empty GitHub repo (`nestharus/server-manager`) is confirmed reachable via `gh`.
- Reference repos are cloned locally into `.refs/` during this range to support the next platform decisions.
- The monorepo is then initialized locally and pushed as initial commit `b6a0421`.
- Early API service scaffolding under `services/api` proves the reference architecture is translatable into the new repo shape.
- A first real Phase 1 infra branch is later built:
  - `infra/` and `k8s/` are scaffolded
  - CodeRabbit is run multiple times on the infra diff
  - the amended commit message ends up as `feat: Phase 1 foundation — OpenTofu + Vultr VKE + Flux + monitoring`
- But this should not be overstated as final deployment:
  - it is implementation draft code
  - the environment model was still being re-researched
  - the later `base-application` discovery exposes a deeper architecture mismatch that forces another proposal/research cycle
- Planning artifacts also become a real deliverable in their own right:
  - `plans/legacy/base-application-index.md` is created
  - `plans/initiative-map.md` is created
  - by this point, planning has been decomposed into 19 initiatives across 6 phases with a stated critical path
- Late in the session, direct merges into `main` are explicitly allowed and several initiative/planning branches are merged there.
- But the end of the session substantially undermines trust in the repository as a source of truth:
  - overlapping agents were run in the same worktree
  - some late commits mixed outputs from unrelated tracks
  - the user ultimately decided the state was not trustworthy enough to preserve
  - the repository was force-reset to an empty root commit (`4250663`) with the intention of replaying the work correctly
- So the final draft has to separate:
  - durable decisions and research conclusions from the conversation
  - implementation artifacts that briefly existed
  - implementation artifacts that survived only inside an untrusted repo history

## User Corrections And Decision Changes

- The user supplied bot token and guild ID, but there was no platform decision beyond local setup.
- Redirect URI / client-secret style OAuth concerns were explicitly ruled out for the local bot-control use case.
- The discovery that ticketsbot.net had been shut down reframed the "broken support integration" problem from debugging to replacement planning.
- Reusing the existing `HumilityTicketBot` application token in tickets.bot v2 exposed a migration mismatch: Discord-side bot identity remained the same while vendor-side panel state did not.
- The user was open to Railway if hosting was needed, but this was still a convenience suggestion rather than a researched platform decision.
- The later reset shows that this phase let infra choices harden before the workflow had earned them.
- The reset also imports a stricter repo operating model from other projects, including explicit research/proposal/risk gates and live-server mutation rules.
- Humility-specific synthesis also strengthens the retention expectation: active records and long-lived operational history both matter.
- The user later supplies decisive platform guidance:
  - use Python rather than Rust
  - use FastAPI
  - include UI in v1
  - treat the repo as a monorepo
- The user also explicitly says that root should not directly host Python or JavaScript application code.
- During implementation, the user also enforces the CodeRabbit CLI workflow from `ai-workflow`: rerun until clean and keep the diff represented as one squashed/amended commit.
- The user later supplies infrastructure credentials and external platform artifacts directly:
  - Vultr API key
  - Vultr SSH key id
  - legacy platform specification documents from Windows downloads
- Additional later corrections from the user are load-bearing:
  - staging is not for always-on QA by default; tests and intent should already cover most validation
  - dev can host E2E and LLM-assisted UI QA
  - staging should exist primarily for release-candidate benchmarking and load/performance validation
  - OpenTofu should not swallow all infrastructure concerns; Crossplane and GitOps are expected to carry a real share of the provisioning model
  - RFQ-style S3 artifact compromises are not acceptable here; proper artifact stores should be used instead
  - references to RFQ / LAMA-AI should not remain anywhere in this repository because that is a separate company/context

## Open Platform Questions

- If a custom daemon replaces Gather/ticketsbot, where should it run?
- What persistence layer should own application/ticket state once the project moves beyond direct Discord reads?
- How much third-party SaaS should remain at all if the goal is assistant-operated infrastructure?
- Should the system remain a Discord-daemon-plus-SQLite app, or be split into a more formal service architecture?
- Which cloud/runtime/database combination best fits the final product after research and proposal phases complete?
- What OCR architecture best fits the final platform: Google Cloud Vision, a mixed fallback design, or something else?
- How should the earlier daemon-centric proposal be translated into the later API + daemon + web monorepo architecture without losing the validated domain model?
- Exact final provider split after the Vultr pivot and `base-application` discovery: single-provider Vultr, or a mixed model with some services elsewhere
- Exact auth-stack boundary between Pomerium and Smallstep
- How much of the legacy event-driven GitOps/custom control plane survives once Buildkite, Flux, and Crossplane are adopted
- Exact bootstrap path from narrow early-cluster secrets handling to full Infisical-managed secrets without unnecessary rework
- Whether the Phase 1 minimum should already include the platform-cluster/application-cluster split, or only prepare for it
- Exact release-channel implementation: Harbor tag/project conventions, Flux policies, and promotion mechanics
- Final package-registry story for Python/JavaScript dependencies alongside OCI and Helm artifacts

## Chronological Notes

- `0000-0009`
- Platform context is still pre-architecture; the project is operating as a local Discord administration tool.
- `0010-0019`
- Local project management conventions settle around `uv` and a repo-specific `AGENTS.md`, but the platform is still strictly local and bot-token based.
- `0020-0029`
- Live-guild scale begins influencing implementation choices even before any cloud platform work exists.
- `0030-0047`
- The first infrastructure-related fork appears:
  - one path is "keep operating locally with a daemon and simple persistence"
  - another path, not yet articulated, will later push toward a more formal service/platform split
- ticketsbot.net discontinuation also creates a future platform responsibility the project did not initially intend to own.
- `0048-0062`
- The platform story briefly tests a vendor-replacement path (`tickets.bot`), but the outcome is negative from an operations standpoint:
  - vendor-managed panel state is opaque
  - old component ids are incompatible after migration
  - the assistant cannot configure or maintain the vendor dashboard on the user's behalf
- `0063-0111`
- The first self-hosted platform draft emerges:
  - `discord.py` daemon
  - Railway hosting
  - persistent SQLite
  - YAML configuration in git
  - no separate API/web split yet
- This block is the clearest example of the later-criticized build-first drift: concrete runtime and storage choices are implemented before the formal research/proposal/risk pipeline.
- `0112-0146`
- Hard platform reset:
  - local-first thinking is rejected
  - SQLite is rejected for the durable system
  - cloud hosting becomes a requirement
  - platform decisions are deferred until after problem-space research
- Formal research adds durable platform constraints:
  - Discord audit logs only cover about 45 days, so system-owned records matter
  - modern Discord modal/component capabilities are stronger than initially assumed
  - vendor EOL risk is a core platform hazard, not a one-off issue
- `0147-0174`
- Platform scope expands beyond basic Discord workflow hosting:
  - screenshot uploads and OCR processing enter the architecture
  - retention expectations push the system further away from throwaway/local storage
  - OCR research shows MVP spend is negligible, so platform choice should optimize correctness, validation, and simplicity instead
- `0175-0240`
- Formal proposal/risk loop establishes a concrete but still unstable platform draft:
  - Railway + Supabase
  - durable Postgres-backed state
  - mixed OCR pipeline
  - staging/production split
- Risk loops matter here because they surface real platform tensions:
  - too much durability machinery for Humility's immediate scale
  - disagreement over DB-enforced append-only vs simpler single-writer assumptions
  - proposal shape validated in many respects, but not fully LOW-risk before new platform inputs arrive
- Late user inputs then trigger a platform pivot before the risk loop cleanly closes:
  - private GitHub repo established
  - monorepo accepted
  - FastAPI + discord.py + TanStack chosen
  - reference repos cloned for structure patterns
- `0241-0279`
- Platform and repo structure become concrete:
  - root becomes orchestration/documentation only
  - `services/api` holds the FastAPI mutation gateway
  - `services/discord` holds the Discord gateway adapter
  - `apps/web` is reserved for the TanStack frontend
  - reference tooling from `ai-workflow` and `ui-designer` begins shaping lint/test/review expectations
- The private GitHub repository is initialized and pushed, which makes the monorepo decision durable.
- Process caveat: implementation scaffolding starts even though the previous proposal cycle had unresolved scope-risk findings, so the structural direction is stronger than the exact validation state.
- `0280-0352`
- The monorepo starts carrying real validated code, not just scaffolding:
  - `services/api` gets the first implemented layered slice
  - FastAPI endpoints, service layer, repository abstraction, and DI wiring are exercised under test
- The implementation workflow also proves out the chosen review/tooling stack:
  - separate test/code agent pattern
  - local pytest verification
  - CodeRabbit CLI loop with amend/squash behavior
- This range ends with the first notable platform doubt after the reset: the user starts questioning Supabase, setting up the next hosting/database pivot.
- `0353-0367`
- Hosting/database pivot starts in earnest:
  - Supabase is rejected as copied from another project rather than justified here
  - Railway Postgres is briefly favored because the project only clearly needs Postgres
  - Railway itself is then challenged on cost against Vultr and possibly Hetzner
  - self-hosted Postgres on a cheap VPS becomes part of the option set
- The platform scope then expands dramatically when four legacy enterprise docs are introduced and converted into markdown under `plans/legacy/`:
  - `auth-v5.md`
  - `expansion-plan.md`
  - `gitops.md`
  - `most-of-platform-v2.md`
- Those docs shift the infrastructure question from "where should this bot run?" to "how much of a broader enterprise platform needs to be modernized and decomposed for this application?"
- The user also flags modernization directions that will matter later:
  - Buildkite instead of Dagger
  - Flux instead of Argo
  - possible provider evaluation beyond Vultr
- `0368-0435`
- Legacy platform decomposition begins in earnest:
  - 4 large legacy platform docs are decomposed individually with `gpt-xhigh`
  - those decompositions are merged into `plans/unified-platform-index.md`
  - the merged result resolves 13 cross-document conflicts and defines 8 platform phases
- Critical platform insight from the merge:
  - the minimum platform required to run `server-manager` is much smaller than the full enterprise platform
  - the Discord bot needs only the early foundation/bootstrap phases, not the whole future platform from day one
- Additional research in this range refines major platform choices:
  - Hetzner vs Vultr
  - Buildkite vs legacy CI/control-plane assumptions
  - self-hosted/object-storage options
  - Pomerium/Smallstep scope overlap
  - RFQ auth research is mined, but the user explicitly chooses the heavier/more robust auth stack for this project instead of RFQ's lighter stack
- `0436-0473`
- The merged/indexed platform work is turned into a concrete first implementation phase.
- Durable decisions locked in this range:
  - Hetzner over Vultr
  - k3s via kube-hetzner
  - OpenTofu for IaC
  - Flux for GitOps
  - Buildkite for CI
  - Authentik + OPAL/Cedar + Pomerium + Smallstep + Infisical + Cloudflare for auth/security/edge
  - Hetzner Object Storage with SeaweedFS fallback
- `plans/proposals/phase1-foundation.md` is written and then passes 3x risk with LOW/LOW/LOW, clearing the way for real infra implementation.
- This range also adds AIOps direction:
  - StackStorm
  - `droid` as an internal AI service
  - z.ai default with MiniMax as a fallback path
- `0474-0575`
- The risk-cleared foundation plan is actually implemented, but implementation immediately surfaces provider reality:
  - `infra/` and `k8s/` are scaffolded
  - CodeRabbit is run repeatedly on the infrastructure branch
  - Hetzner account limits and operator friction become concrete blockers
  - Contabo is researched as a cheaper escape hatch but is not trusted enough for the intended production Kubernetes role
- Practical direction therefore pivots from Hetzner/kube-hetzner to Vultr VKE.
- This same range also begins redefining the environment model:
  - `dev` emerges as a persistent application-development target
  - `production` remains persistent
  - `staging` starts losing its "always-on QA" meaning
- `0576-0605`
- The environment model is explicitly re-researched and clarified:
  - `dev` is persistent and used for app development, E2E, and LLM video QA
  - `staging` becomes on-demand release-candidate benchmarking infrastructure
  - `production` is persistent and promotion-only
- A revised proposal/risk cycle starts because the environment and provider assumptions changed enough to invalidate the earlier clean story.
- Then `base-application` changes the architecture again:
  - Terraform/OpenTofu is reframed as external bootstrap only
  - Flux/Helm/Kustomize are separated as cluster configuration machinery
  - Crossplane becomes the in-cluster provisioning layer
  - the platform is expected to grow toward a platform-cluster-plus-application-cluster model rather than a single flat cluster
- `0606-0620`
- Supply-chain and delivery concerns are pulled into the platform plan:
  - vulnerability scanning is now a required capability
  - internal and external packages need controlled artifact storage
  - release artifacts and release channels become first-class design concerns
- Existing RFQ research is mined, but the user rejects its S3-centered compromises.
- Durable correction in this range:
  - Harbor becomes the preferred unified artifact store
  - Trivy is the practical baseline for vulnerability scanning
  - release channels are expected to map cleanly onto environment promotion paths
- The planning model is then reorganized into a formal initiative portfolio:
  - 19 initiatives
  - 6 phases
  - a critical path that puts platform bootstrap, GitOps foundation, secret management, and application-cluster provisioning ahead of product-facing bot deployment
- `0621-0659`
- Execution shifts from branch accumulation to direct integration:
  - the user explicitly allows merging ready work directly into `main`
  - planning branches and feature branches are merged
  - Phase 1 initiative proposals are written in parallel and all nine risk assessments return LOW
- Product-strategy templates are generalized in parallel, but the durable platform takeaway here is the initiative split itself:
  - Platform Bootstrap
  - GitOps Foundation
  - Secret Management
  - Application Cluster Provisioning
  - then later artifact, CI/CD, database, identity, observability, and application-facing initiatives
- `0660-0705`
- Database and audit architecture become much more precise:
  - Atlas wins schema management
  - SQLAlchemy Core wins the default data-access layer
  - testcontainers/template DBs win E2E isolation
  - seeded database images become part of the release/testing conversation
- The activity/audit model also changes the platform's data assumptions:
  - action records and state-change records become explicit
  - optimistic locking is tied to activity hashes/ETags rather than row version columns
  - after addenda for atomicity and determinism, this proposal reaches 3x LOW
- Phase 1 infrastructure also keeps moving in this window:
  - GitOps acceptance tests are written
  - a multi-environment `k8s/` structure is created
  - but these implementation artifacts later fall inside the portion of the session the user treats as process-compromised
- `0706-0755`
- This is the collapse-and-reset phase.
- Important facts:
  - Crossplane manifests are generated
  - product strategy is run incorrectly as a collapsed workflow and the user forces a restart
  - overlapping agent runs and cleanup/revert commands make the state untrustworthy
  - the user explicitly says the project must be restarted from scratch and replayed correctly with worktrees
  - `main` is force-pushed to an empty root commit
- Draft implication:
  - Crossplane/two-tier architecture remains a durable design direction from research/proposals/reference analysis
  - but late concrete manifest/code outputs from this chaotic phase should not be treated as reliable implementation evidence

## Modernized Platform Direction

- Legacy platform docs are decomposed into:
  - 188 components
  - 117 architectural decisions
  - 76 implementation units
  - 58 cross-document dependencies
  - 46 outdated/questionable flags
- A merged `plans/unified-platform-index.md` then resolves the legacy conflicts into a phased modernized platform direction.
- Key merge resolutions in this range:
  - Buildkite wins over older CI engines and custom Dagger-centered assumptions
  - OpenTofu wins over older Terraform/controller/manual mixtures
  - Flux wins over Argo for GitOps
  - Git remains the desired-state source
  - zero-trust assumptions remain
- The merged plan defines 8 platform phases, with the Discord bot only requiring the first two phases of critical-path platform bootstrap.
- Later this broad modernization work is reorganized into a more execution-friendly initiative map:
  - 19 initiatives
  - 6 phases
  - explicit "ready to start now" initiatives
  - a dependency graph instead of one undifferentiated platform backlog
- Phase 1 of that initiative map is especially important because it gives the final platform narrative a concrete control-plane-first shape:
  - Platform Bootstrap
  - GitOps Foundation
  - Secret Management
  - Application Cluster Provisioning

## Initiative Map

- The late-session initiative map is the cleanest summary of how platform work was eventually decomposed.
- Phase 1:
  - Platform Bootstrap
  - GitOps Foundation
  - Secret Management
  - Application Cluster Provisioning
- Phase 2:
  - Artifact Management
  - CI/CD
  - Release Management
  - Database
  - Observability
- Later phases then layer on edge/networking, identity/access, API and Discord application surfaces, web UI and activity tracking, then benchmarking/dynamic environments/security hardening/AIOps.
- Critical-path implication:
  - the Discord/server-manager application is downstream of platform control-plane, delivery, and database initiatives rather than being the first thing to ship

## Hosting Provider Evolution

- The provider conversation broadens beyond Railway:
  - Vultr is attractive because it offers VKE, managed Postgres, and object storage with good provider support
  - Hetzner is attractive on raw compute/storage price but lacks managed Kubernetes control plane and managed Postgres
- Early research conclusion in this range:
  - Vultr is operationally easier for the robust/K8s path
  - Hetzner is cheaper but increases ops burden
  - Hetzner's apparent 5-server cap is an account limit, not a hard product limit
- The next-phase decision is initially still Hetzner, because the user is open to self-managing the control plane in exchange for lower cost.
- That decision does not hold:
  - implementation hits account-capacity friction
  - the user explicitly reacts negatively to Hetzner operational hassle
  - the branch is rewritten toward Vultr VKE
- By the end of the provider-churn block, the practical implementation direction is Vultr, even though the broader architecture is still being reworked by `base-application` discoveries.

## Object Storage Direction

- Legacy S3 assumptions are reopened.
- Research in this range suggests:
  - default to provider-native object storage if possible
  - if self-hosting becomes necessary, SeaweedFS is the most attractive self-hosted S3-compatible candidate among the options considered
  - Garage is lighter but less feature-complete
  - MinIO has strong S3 fidelity but licensing concerns
- The next-phase practical choice is initially Hetzner Object Storage first, with SeaweedFS retained as a fallback if provider-native storage proves limiting.
- After the move away from Hetzner, provider-native storage assumptions need to be re-grounded on Vultr and/or the later Crossplane-managed platform design.
- Later delivery-planning research also distinguishes object storage from artifact storage:
  - S3-compatible buckets may still exist for object storage needs
  - but release artifacts, package registries, and image registries should live in purpose-built artifact systems rather than S3 hacks

## Artifact Management And Release Channels

- This surface becomes explicit only after the `base-application` and initiative-map phase.
- Durable direction in this range:
  - Harbor is the preferred unified artifact store
  - Trivy provides baseline vulnerability scanning
  - package, image, chart, and release artifact handling should be treated as supply-chain infrastructure, not incidental CI details
- Release-management ideas imported from RFQ survive in adapted form:
  - environments correspond to release/promotion paths
  - promotions should be atomic and serialized
  - downstream environments should watch the correct promoted artifact stream
- But the storage substrate is corrected:
  - do not use S3 as a fake artifact registry
  - use purpose-built registries/stores and let Flux/automation consume them

## Trust Boundary

- The conversation produces a large amount of valuable design material, research, proposals, and even some implementation.
- But the session also establishes a hard trust boundary:
  - once overlapping agents start writing in the same checkout without worktree isolation, implementation provenance becomes suspect
  - late-session resets, force-kills, `git clean`, and force-pushes make it impossible to treat the repository history itself as authoritative
- Therefore this draft should treat:
  - research conclusions, user corrections, and risk-cleared design choices as durable source material
  - late implementation state only as tentative evidence unless it clearly predates the process failure

## Auth And Policy Direction

- RFQ's lighter auth choices are treated as informative but not authoritative for this project.
- The user explicitly states the robust/full-stack preference here:
  - Authentik over Logto
  - OPAL/Cedar over Casbin
  - Pomerium definitely included
  - Smallstep likely included, though overlap with Pomerium needs research
- Research in this range clarifies the layer split:
  - Logto + Casbin is validated for lighter application stacks
  - Authentik + Pomerium + OPAL/Cedar + possibly Smallstep is the intended heavier platform stack here
- Later targeted research also notes that modern Pomerium can absorb SSH access use cases that older specs may have assigned to Smallstep, so the final Smallstep boundary still needs care.
- In the next phase, the user locks the robust stack fully:
  - Authentik
  - OPAL/Cedar
  - Pomerium
  - Smallstep retained because full PKI is desired
  - Infisical for long-term secret management
  - Cloudflare at the edge

## Phase 1 Foundation

- A dedicated `plans/proposals/phase1-foundation.md` proposal is written for the minimum infrastructure bootstrap.
- Key choices in that proposal:
  - Hetzner Cloud
  - k3s via `kube-hetzner`
  - OpenTofu + `hcloud`
  - Flux CD
  - kube-prometheus-stack
  - Hetzner Object Storage
  - intentionally narrow bootstrap secrets handling before the longer-term Infisical target
- The Phase 1 proposal passes 3x `claude-opus` risk with LOW/LOW/LOW.
- The implementation that follows does not stay faithful to the initial Hetzner-based proposal:
  - provider assumptions are revised to Vultr
  - environment model expands to `dev`, `staging`, and `production`
  - then `base-application` reveals that the real target architecture likely needs a platform cluster with in-cluster Crossplane provisioning
- So Phase 1 is important as a milestone, but not stable as originally written.
