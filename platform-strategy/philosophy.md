# Platform Philosophy

These principles govern how infrastructure decisions are made for this project. They complement the product philosophy — which governs what the application does and how it treats users — by governing the platform layer that makes the application runnable, deployable, and operable.

Every principle is derived from the platform problem definition and the concrete realities of Humility's operating environment: a single operator, a small community that nonetheless demands real uptime, a product with durable state and multiple surfaces, and a budget that cannot absorb enterprise-grade overhead.

## Principles

### Principle 1 — One Operator Is the Design Point

The platform must be operable by a single person alongside their product work. If a component requires a second operator to run safely, demands more ongoing attention than one person can sustain, or fails silently in ways that only surface under active monitoring, it is wrong-sized for this project. Every platform component carries an implicit staffing requirement — that requirement must be one.

**Because:** Humility has one administrator who also owns the product. There is no platform team, no on-call rotation, no second pair of eyes. A platform that is architecturally sound but operationally demanding for one person will either consume the product roadmap or decay unattended. The problem definition's capability dead zone exists precisely because the operator pool is this small.

**Applies when:** Evaluating any new platform component, control plane, or operational process. Choosing between a self-hosted tool that requires care and a managed service that does not. Deciding whether to add a new environment, monitoring surface, or reconciliation layer.

### Principle 2 — The Platform Serves the Product

Every platform component must trace to a product capability it enables. Platform work that cannot name the product workflow it unblocks is overhead. When platform scope threatens to expand, the burden of justification falls on the platform work, not on the question of why it is needed.

**Because:** The platform research repeatedly demonstrated scope creep: a question about where to run a Discord bot expanded into 19 initiatives across 6 phases covering bootstrap, GitOps, secrets, identity, observability, and more. Each layer was individually defensible. Together, they threatened to absorb the roadmap before the product delivered value. The platform exists to run the application — applications, tickets, chapters, activity tracking, the API, the web UI. Platform investment that does not serve those surfaces competes with them for the same operator's time.

**Applies when:** Prioritizing platform work against product work. Evaluating whether a platform capability belongs in the current phase or a later one. Deciding whether to adopt a tool because the product needs it now or because the platform architecture calls for it eventually.

### Principle 3 — Buy Operator Time, Not Independence

Prefer managed services over self-hosted alternatives when managed services reduce total operator attention. Accept provider dependence as the price of reduced burden, but keep state portable and interfaces standard so that migration is painful but possible — not architecturally blocked. Do not build abstraction layers to insulate against hypothetical provider switches at the cost of real operator time today.

**Because:** The platform conversation pivoted through Railway, Hetzner, and Vultr. Each pivot was driven by a real concern — cost, account limits, operational friction — but the pivots themselves were expensive. The lesson is not "avoid providers" or "abstract everything." It is that dependence is acceptable when it buys operator time, and migration is survivable when state is exportable and interfaces are standard (S3-compatible storage, Postgres-compatible databases, OCI-compatible registries). The dead zone makes independence expensive: self-hosting everything to avoid lock-in produces exactly the operational burden a one-person team cannot carry.

**Applies when:** Choosing between a managed service and a self-hosted equivalent. Deciding how much provider-specific configuration to accept. Evaluating whether a migration path exists before committing to a provider for a stateful service. Resisting the urge to build a portability layer before the first provider has proven inadequate.

### Principle 4 — Environments Are Contracts, Not Copies

Each environment is a distinct set of promises about persistence, data realism, failure tolerance, and cleanup. Define environments by what they promise operators and the product, not by what infrastructure they contain. Do not create an environment unless its contract differs meaningfully from an existing one. Prefer on-demand environments over always-on environments when the contract permits it.

**Because:** The research redefined environments multiple times — staging went from always-on QA to on-demand release-candidate benchmarking, dev became the persistent place for application development and E2E testing, and production stayed persistent and promotion-only. Each redefinition happened because the team got more precise about what each environment was actually for. Environment cost is not just compute — it is the operational surface area of maintaining secrets, data, monitoring, DNS, and cleanup for each distinct contract. An environment that exists without a clear distinct purpose is pure overhead.

**Applies when:** Proposing a new environment type. Deciding whether staging needs to be always-on. Evaluating whether dev and production are sufficient for the current product phase. Determining what data, monitoring, and access guarantees each environment carries.

### Principle 5 — Declare Intent, Respect Drift

Infrastructure should be declarative where the value justifies the complexity: cluster configuration, service deployment, environment provisioning. But lived infrastructure accumulates state that declarations cannot fully capture — retained data, external identities, provider-specific behavior, migration history. Treat divergence between declared and lived state as a normal condition to manage, not a defect to eliminate.

**Because:** The platform research kept discovering layers where intent and reality separated. A single-cluster story became a platform-cluster-plus-application-cluster model. Database thinking evolved from local persistence to durable Postgres with versioned schema artifacts. Each attempt to make the platform more reproducible added another control surface — bootstrap infrastructure, Git-managed desired state, cluster reconcilers, environment claims — and each surface was another place where lived state could diverge from declared intent. Reproducibility is valuable, but pretending that `tofu apply` from a clean slate is equivalent to operating a system with two years of retained data is dangerous.

**Applies when:** Choosing the boundary between OpenTofu (external bootstrap), Flux (in-cluster reconciliation), and Crossplane (in-cluster provisioning). Deciding how much infrastructure to codify versus manage operationally. Planning migrations where the target state is declarative but the path from current state is not. Evaluating whether a manual operational step should be automated or simply documented.

### Principle 6 — Observability Within Attention Budget

Monitoring, alerting, and logging must fit inside the attention a single operator can actually spend. A signal nobody checks is waste. An alert that fires routinely becomes noise. Prefer fewer, high-signal channels over comprehensive dashboards. When adding a new observability surface, identify which specific failure mode it catches that nothing else does, or which existing surface it replaces.

**Because:** The platform direction accumulated monitoring, logging, vulnerability scanning, deployment status, artifact provenance, and audit records across multiple environment types. That is a matrix of signals that a staffed platform team tunes and triages. A single operator cannot maintain that matrix. Low-volume incidents are especially dangerous in this environment because they leave little data for tuning alert thresholds. Off-hours failures, duplicated telemetry, and multi-environment signal sprawl all consume attention the operator does not have. The product philosophy's Principle 2 (Reduce Burden) applies to the platform's own observability: if monitoring creates a new recurring obligation, it must eliminate a larger one.

**Applies when:** Choosing which metrics, logs, and alerts to deploy. Deciding whether a new environment type needs its own monitoring stack or shares with an existing one. Evaluating whether a vulnerability scanner, audit log, or status dashboard is worth the ongoing attention cost. Setting alert thresholds that distinguish actionable signals from background noise.

### Principle 7 — Cost Proportionate to Community

Platform spending must be justifiable against an ~88-member community, not against enterprise traffic or growth projections. When evaluating infrastructure options, compare total cost of ownership — including operator time spent on maintenance, debugging, and migration — not just the compute line item. A more expensive managed service that saves hours of weekly maintenance is cheaper than a free tool that demands regular care.

**Because:** The platform sits in a dead zone between hobby tolerance and enterprise expectations. Raw compute price drove the initial Hetzner interest, but account limits and operator friction made the cheaper option more expensive in practice. The community's scale means the platform will never amortize complex infrastructure through traffic volume. Every dollar and every hour spent on platform overhead is a dollar or hour not spent on the product that serves the community. Cost evaluation that ignores operator time systematically underprices self-hosted options and overvalues sticker-price savings.

**Applies when:** Comparing managed versus self-hosted services. Evaluating whether a platform component is justified at current scale. Deciding whether to adopt a free-tier service with operational strings attached or pay for a service that reduces burden. Setting budgets for compute, storage, and third-party services.

### Principle 8 — Change Is Expected; Churn Is Not

Provider pivots, tool replacements, and architectural corrections will happen over the lifetime of this platform. Design for survivable change by keeping interfaces standard and state exportable — not by building portability abstractions ahead of need. But distinguish deliberate migration from churn. A deliberate migration is planned, justified by a concrete failure of the current choice, and executed once. Churn is repeated pivoting driven by incomplete evaluation or premature commitment. Before switching, complete the evaluation that the current choice failed.

**Because:** The research pivoted providers three times (Railway to Hetzner to Vultr), redefined the environment model twice, and restructured the provisioning architecture when the base-application reference revealed a deeper pattern. Some of these pivots were necessary corrections; others were avoidable if the initial evaluation had been more thorough. The cost of a provider switch is not just the migration work — it is the invalidation of every decision downstream of the provider assumption. The platform philosophy must accept change as normal without treating constant re-evaluation as normal.

**Applies when:** Evaluating whether to switch a provider, tool, or architectural pattern. Deciding how deeply to evaluate a choice before committing. Determining whether dissatisfaction with a current tool reflects a real inadequacy or an incomplete adoption. Planning migration timelines and rollback strategies.

### Principle 9 — Complexity Must Be Earned

Every layer of platform abstraction — control planes, reconcilers, provisioning engines, policy frameworks — must justify its existence against the actual current workload, not against projected future needs. The two-tier cluster model, GitOps reconciliation, and in-cluster provisioning are valid architectural targets documented in the research, but each layer is adopted when the product workload requires it, not before. A running single-cluster deployment that serves the product today is worth more than a correctly-architected multi-cluster design that is still being bootstrapped.

**Because:** The platform research produced a 19-initiative, 6-phase roadmap. That roadmap describes a complete platform. But the product needs a running system before the platform is complete. The reference architecture's platform-cluster-plus-application-cluster model is a legitimate design for multi-environment isolation, but it is also the kind of architectural sophistication that can delay product delivery indefinitely if treated as a prerequisite rather than a target. The product philosophy's Principle 11 (Right-Sized Design) applies with equal force to the platform: solve the actual problems at the actual scale. Adopt the next layer of complexity when the current layer's limits are concretely blocking product work.

**Applies when:** Deciding whether to implement a platform layer now or defer it. Evaluating whether the current deployment model is blocking the product or merely less elegant than the target architecture. Choosing between a simpler interim approach and the architecturally correct long-term approach. Determining the minimum platform that unblocks the next product milestone.

## Principle Interactions

### Principle 1 (One Operator) and Principle 3 (Buy Operator Time)

**Reinforcement:** These principles reinforce each other directly. One Operator sets the constraint — the platform must be runnable by one person. Buy Operator Time provides the primary strategy for meeting that constraint — choose managed services that reduce the operator's burden, even at the cost of provider dependence.

**Edge case:** When a managed service is itself complex to configure or has poor documentation, it may add operator burden rather than reducing it. Evaluate managed services by actual operational experience, not by the promise of being "managed."

### Principle 2 (Platform Serves Product) and Principle 9 (Complexity Must Be Earned)

**Reinforcement:** Both principles resist premature platform investment. Principle 2 asks whether a platform component traces to a product capability. Principle 9 asks whether it is needed now. Together they form a two-part test: Does this platform work unblock the product? And does it unblock the product at the current stage, not a hypothetical future stage?

**Edge case:** Some platform work is genuinely foundational — it does not directly unblock a single feature but makes all subsequent features possible (e.g., a working deployment pipeline). Principle 2 permits this when the platform work is on the critical path to any product delivery. Principle 9 still applies: build the minimum viable foundation, not the architecturally complete one.

### Principle 3 (Buy Operator Time) and Principle 8 (Change Expected, Not Churn)

**Tension:** Buying operator time by committing to managed services increases the cost of switching later. If the provider fails or becomes too expensive, the migration is harder precisely because the platform leaned in.

**Guidance:** Accept this tradeoff explicitly. Managed services are the right default for a one-person team. But before committing to a stateful managed service (database, object storage, registry), verify that the data can be exported in a standard format and that the interface is not proprietary. The goal is not zero switching cost — it is survivable switching cost. A migration that takes a weekend is acceptable. A migration that requires rewriting the application is not.

### Principle 4 (Environments Are Contracts) and Principle 6 (Observability Within Attention Budget)

**Tension:** Each environment contract implies its own observability requirements — production needs real alerting, dev needs enough visibility to debug, on-demand environments need status visibility during their lifetime. More environments mean more observability surface.

**Guidance:** Share observability infrastructure across environments wherever the contract permits it. Production gets dedicated alerting. Dev shares a monitoring stack with production but with lower alert urgency. On-demand environments inherit monitoring configuration from their template but do not add persistent alert channels. The attention cost of an environment includes its observability cost — factor this into the decision of whether the environment is worth creating.

### Principle 5 (Declare Intent, Respect Drift) and Principle 9 (Complexity Must Be Earned)

**Tension:** Declarative infrastructure improves reproducibility and safety, but each declarative layer (OpenTofu, Flux, Crossplane) is itself a platform component with learning curve, failure modes, and operational overhead. Full declarative coverage is the correct long-term target but may be premature complexity now.

**Guidance:** Adopt declarative tooling in order of value-to-the-operator. Start with the layer that reduces the most manual work or risk (likely cluster provisioning via OpenTofu and service deployment via Flux). Add in-cluster provisioning (Crossplane) when the product needs multiple environments that must be programmatically created. Document any operational steps that remain manual — they are not defects, they are complexity that has not yet been earned.

### Principle 7 (Cost Proportionate) and Principle 1 (One Operator)

**Reinforcement:** Both principles point toward the same decision: do not over-invest. Principle 7 constrains financial cost against the community's scale. Principle 1 constrains operational cost against the operator's attention. Together they define the budget envelope: the platform can spend what the community can justify in money and what the operator can sustain in time.

**Edge case:** Occasionally the cheapest financial option is the most operationally expensive (self-hosting everything) and the least operationally expensive option is financially disproportionate (enterprise SaaS). The right choice lives between these extremes. When the two principles conflict, Principle 1 wins — operator time is the harder constraint to relax.

### Principle 2 (Platform Serves Product) and Principle 6 (Observability Within Attention Budget)

**Reinforcement:** Observability that does not serve product reliability is platform overhead. Both principles demand that monitoring justify its existence: Principle 2 asks what product capability it protects, and Principle 6 asks whether the operator will actually use it. Monitoring that protects a product-critical path (the Discord daemon staying connected, the API responding, the database accepting writes) passes both tests. Monitoring that covers a platform-internal process with no direct product impact fails Principle 2 and probably fails Principle 6 as well.

## Expansion Guidance

When the platform encounters new infrastructure decisions not yet covered by the problem definition, apply these principles as follows:

**Start with Principle 1.** Can one person operate this? If the answer is "yes, but only if they also give up something else," identify what they are giving up and whether the tradeoff is acceptable.

**Apply Principle 2 immediately.** What product capability does this platform work enable? If the answer is vague ("future flexibility," "architectural correctness"), defer the work until a product need makes it concrete.

**Use Principle 9 as the scheduling rule.** Even when a platform component is justified by Principles 1 and 2, Principle 9 determines when to adopt it. Build it when the product workload requires it, not when the architecture diagram calls for it.

**Check Principle 7 before committing.** Will this cost more than the community can justify? Include operator time. A component that is free in dollars but costs a weekend of setup every quarter is not free.

**When choosing between providers or tools, apply Principles 3 and 8 together.** Buy operator time (Principle 3) — prefer the option that reduces ongoing burden. But evaluate thoroughly before committing (Principle 8) — do not pivot to a new tool before understanding why the current one failed or before confirming the replacement actually solves the problem.

**When adding observability, apply Principle 6 strictly.** Name the failure mode. Name the action the operator would take when the signal fires. If you cannot name both, the signal is not ready to deploy.

**When principles conflict on the new surface,** use the interaction guidance above. If the conflict is novel — not covered by existing interactions — that is a signal that the philosophy may need a new interaction entry rather than that the principles should be overridden. The product philosophy's principles remain in force alongside these: platform decisions must not violate product principles (especially Principle 1 — Live System, Principle 2 — Reduce Burden, and Principle 11 — Right-Sized Design).
