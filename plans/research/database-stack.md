# Database Stack Research for FastAPI + PostgreSQL

As of April 14, 2026.

## Bottom line

For this platform, the strongest fit is a **SQL-first PostgreSQL stack**:

- **Schema evolution**: versioned SQL migrations in Git, with AI authoring or drafting SQL directly.
- **Migration control plane**: **Atlas** is the strongest current companion tool if the team wants migration hashing, CI linting, drift checks, and optional diff generation without making SQLAlchemy metadata the source of truth.
- **Application data access**: **`psycopg` 3 + typed row factories + Pydantic/dataclass DTOs**, not a heavyweight ORM.
- **E2E reset model**: keep one migrated+seeded baseline per CI run, then clone per scenario using PostgreSQL template-database mechanics or restore from a custom dump.

The key 2026 shift is that **AI-generated migrations change the scoring**. Tools that keep the reviewed artifact as plain SQL age better than tools that hide schema intent behind ORM metadata or code-generation DSLs. AI is much better at producing and reviewing explicit SQL than at safely manipulating ORM internals, especially once PostgreSQL-native objects enter the picture.

## 1. Migration tools

### Alembic

Alembic remains the default migration answer in many FastAPI projects because it is mature, widely understood, and integrates cleanly with SQLAlchemy-based applications. It can autogenerate candidate migrations from SQLAlchemy metadata, and it still works well when the database model is already expressed in SQLAlchemy Core or ORM models.

The problem is fit, not capability. For this platform:

- Alembic's strongest workflow assumes **SQLAlchemy metadata is authoritative**.
- Its autogeneration is explicitly a **candidate** workflow, not a full schema compiler.
- Generated migrations are **Python migration scripts**, not plain SQL.
- Custom types and advanced constructs push the system into rendering hooks, custom imports, and migration-time Python code conventions.

That makes Alembic less attractive when the team wants:

- SQL as the review artifact
- minimal ORM coupling
- PostgreSQL-native features without framework indirection
- migrations that AI can author and humans can review line-by-line

Alembic is still viable if the platform intentionally standardizes on SQLAlchemy Core and accepts that migrations are Python programs. It is a weaker fit if the goal is to keep schema management decoupled from SQLAlchemy-style metadata ownership.

### Atlas

Atlas is the strongest modern option if the goal is **SQL-first migrations with CI-grade safety rails**.

What Atlas does well:

- Supports **versioned migrations** as explicit SQL files in sequence.
- Maintains **`atlas.sum`** to detect directory tampering/history drift.
- Can generate migration diffs from SQL/HCL/ORM schema definitions when desired, but the output is still reviewable migration files.
- Has strong CI/CD workflow support around linting, drift checks, migration integrity, and isolated test databases.
- Atlas explicitly documents AI-assisted PR workflows in CI, which is materially relevant here.

Why Atlas fits this platform better than Alembic:

- The migration artifact can stay **raw SQL**.
- Atlas can be used as a **validator/planner**, not as the owner of an ORM model graph.
- It gives the team a better answer to "how do we let AI draft migrations without blindly trusting them?"

The main risk is licensing and feature coverage. Atlas is open-core. The community edition covers core inspection, diffing, and versioned migrations, but several advanced PostgreSQL features and some stronger linting rules are Pro-gated. In particular, Atlas documents Pro-only schema awareness/check coverage for several PostgreSQL-native objects and checks, including views, functions, extensions, triggers, RLS/policies, and some locking/concurrency lint rules. That means Atlas is excellent if:

- the team is willing to pay for Atlas Pro, or
- the team mainly uses Atlas as a SQL migration runner/integrity tool and is comfortable handling some advanced PostgreSQL objects more manually.

### Raw SQL migrations written with AI

This is the most natural fit for the stated constraints.

Strengths:

- Best reviewability: the PR shows the exact `ALTER TABLE`, `CREATE INDEX`, `UPDATE`, `CREATE FUNCTION`, or `COMMENT ON` statements that will run.
- Best AI ergonomics: LLMs are generally more reliable at drafting and critiquing plain SQL than ORM-specific migration DSLs.
- Best PostgreSQL reach: no translation gap for extensions, enum changes, RLS, triggers, functions, generated columns, or online migration patterns.
- Easiest long-term maintenance: SQL does not require understanding Alembic render hooks or Prisma schema limitations five quarters later.

Risks:

- A raw-SQL-only setup without safety rails makes it easy for AI or humans to ship bad lock behavior, unsafe backfills, accidental table rewrites, or irreversible data mistakes.
- Someone still has to enforce ordering, linear history, environment application state, and review discipline.

So raw SQL is not a complete stack by itself. It is the **best migration artifact**, but it benefits from a companion tool such as Atlas for hashing, apply state, linting, and drift checks.

### Prisma Migrate / Prisma-adjacent approaches

Prisma in 2026 is more capable than the older "ORM only" framing suggests:

- Prisma ORM has `prisma.config.ts` as a central config surface.
- Prisma supports explicit seeding.
- It now has **TypedSQL** for type-safe raw SQL queries built on Prisma Client.
- Prisma can ignore externally managed tables in Prisma Migrate.
- Its SQL views support is becoming more realistic.
- Prisma's newer architecture has reduced dependency on Rust engines.

So Prisma still adds value in 2026, but mostly for **TypeScript-centric teams** that want:

- a single schema DSL
- Prisma Client ergonomics
- generated TS types and query APIs
- a TS-first app/runtime boundary

For this platform, Prisma is a weaker fit:

- The primary backend is **FastAPI/Python**, not Node/TypeScript.
- Prisma introduces a second toolchain and runtime concern for the core service.
- Prisma Migrate still centers the **Prisma schema DSL**, not PostgreSQL SQL, as the primary source of truth.
- When a system leans into PostgreSQL-native features, Prisma often falls back to custom SQL migrations anyway.

That means Prisma still has value in 2026, but not enough value here to justify making it the primary migration/data-access layer for a Python-first platform.

### Decision summary for migration tooling

If the platform wants the cleanest alignment with its stated constraints:

1. **Best overall**: raw SQL migrations in Git, with Atlas providing integrity/lint/apply workflow.
2. **Acceptable fallback**: raw SQL migrations with a thinner runner and stricter review/schema-diff discipline if Atlas licensing or fit is rejected.
3. **Conditional option**: Alembic only if the team is willing to accept SQLAlchemy metadata as an architectural dependency.
4. **Not recommended as primary**: Prisma Migrate for the FastAPI backend.

## 2. Type-safe data access without a full ORM

### Best fit: `psycopg` 3 + typed rows + explicit SQL

For Python in 2026, the cleanest non-ORM path is:

- `psycopg` 3 for connections/transactions
- row factories such as `class_row()` or `namedtuple_row()`
- dataclasses or Pydantic models as DTOs/contracts
- repository/query modules that keep SQL in `.sql` files or clearly bounded Python query strings

This gives:

- direct SQL control
- no ORM unit-of-work model
- predictable transaction handling
- static typing help at the row-mapping boundary
- a clean fit with FastAPI response/request models

This is the simplest answer that preserves both SQL clarity and Python-native ergonomics.

### `sqlc` and SQL-first generated clients

`sqlc` remains one of the strongest SQL-first ideas in the ecosystem: define schema + queries in SQL, generate typed client code, and fail builds when schema changes would break existing queries.

That model is attractive here in principle. The problem is language fit:

- `sqlc` remains strongest in **Go**.
- Kotlin support moved to a plugin.
- Python support is no longer first-class in core docs and is plugin-based.
- The current documented Python path points at a plugin release labeled `alpha`.

So `sqlc` is relevant as a design pattern and excellent if a Go service or TS/other generated client becomes central. It is **not the leading recommendation for the FastAPI service itself** today because the Python path is still less mature than the Go path.

### Prisma TypedSQL

Prisma TypedSQL is a credible 2026 option for **TypeScript** services that want raw SQL with generated types but still want Prisma Client underneath. It narrows one of Prisma's older weaknesses.

But for this platform it does not solve the core mismatch:

- the main service is Python
- using TypedSQL still means buying into Prisma Client and Prisma's Node-centric tooling

It may still be useful in adjacent TS packages in the future, but not as the core access layer for `services/api`.

### SQLAlchemy Core without the ORM

SQLAlchemy Core is lighter than full ORM usage, and some teams successfully use it only as a SQL expression layer. But for this project it is still a liability relative to direct SQL because:

- it keeps the team in the SQLAlchemy abstraction universe
- it tends to pull Alembic and metadata-first workflows back in
- AI-authored diffs are less transparent than explicit SQL

If the team wants to avoid SQLAlchemy-style coupling, then "Core only" is usually a halfway house, not a clean escape.

### Recommendation for data access

Use:

- `psycopg` 3
- explicit SQL
- typed row factories
- Pydantic/dataclass DTO mapping

Do not use a full ORM as the dominant data-access model.

## 3. Test database images and per-scenario reset strategy

This needs two separate decisions:

1. How to create a **baseline database state** quickly in CI.
2. How to reset cheaply **between E2E scenarios**.

### Seeded database images

There are three realistic patterns:

#### A. OCI image that carries SQL/init scripts

This is simple, but startup cost is paid repeatedly because the container still has to initialize and run the migrations/seeds.

Use this only if the baseline is small and startup time is already acceptable.

#### B. OCI image or artifact that carries a **database dump**

This is the best portable baseline artifact.

Recommended shape:

- Run migrations once in CI.
- Apply baseline seed data once.
- Produce a **custom-format `pg_dump` archive** (`pg_dump -Fc`).
- Store that archive as a Buildkite artifact or package it into a small helper image.

Why this is better than shipping a raw `PGDATA` directory:

- `pg_dump`/`pg_restore` are PostgreSQL-supported portability mechanisms.
- `pg_restore` can recreate, clean, and parallelize restore work.
- It avoids filesystem-level brittleness across image/build environments.

#### C. Prebuilt `PGDATA` image snapshot

This can be fastest to start, but it is the most operationally brittle. It couples the artifact to PostgreSQL version details, initialization semantics, and storage layout. It is harder to reason about and less portable than a dump-based artifact.

I would not make a raw `PGDATA` snapshot the main strategy unless restore time becomes a proven bottleneck.

### Per-scenario reset strategy

For Buildkite-driven E2E, the best practical pattern is:

1. Restore the migrated+seeded baseline once into a local PostgreSQL instance for the job.
2. Create a **template database** from that baseline.
3. For each scenario, create a fresh database using `CREATE DATABASE scenario_x TEMPLATE template_e2e`.
4. Run the scenario against its own database.
5. Drop the scenario database after the test.

Why this is the right reset model:

- PostgreSQL database cloning is fast for this use case.
- It gives each scenario isolation without rerunning migrations every time.
- It works well with Buildkite parallelism if each shard or worker gets its own cloned database name.

Operational caveat:

- PostgreSQL documents that no other sessions may be connected to the template database while it is being copied.

That is manageable if the template database is treated as read-never/connect-never after setup.

### Recommended CI/E2E pattern

Recommended stack:

- **Baseline artifact**: `pg_dump -Fc` after migrations + baseline seed.
- **Job bootstrap**: `pg_restore --clean --if-exists --create` into the job-local PostgreSQL service.
- **Scenario reset**: clone from a dedicated template database per job/shard.

This is faster and more reliable than "rerun all migrations for every scenario", and safer than filesystem-level database snapshots.

## 4. Scenario seeding

Treat seeding as three different categories, not one:

### A. Bootstrap/reference data

This is data the application genuinely requires to start or to preserve invariants: enum-like lookup rows, fixed workflow states, system roles, and other stable reference records.

Rule:

- If the app cannot boot correctly without it, version it alongside schema changes.

Usually this belongs in SQL migrations or tightly coupled SQL seed scripts.

### B. Baseline test seed

This is the canonical E2E starting world used for most tests. It should be:

- deterministic
- idempotent or rebuilt from scratch
- versioned in Git
- easy for AI to inspect and modify

Best representation:

- plain SQL files
- `COPY`-based bulk loads where needed
- stable UUIDs / stable keys rather than sequence-dependent assumptions

Build the CI baseline dump from this state.

### C. Scenario delta seeds

Each scenario should add only the minimum extra data needed to express the case under test.

Recommended shape:

- one SQL file per scenario, or
- one small Python fixture layer that executes SQL against a fresh cloned DB

Do not encode scenario state in opaque application-side factory code if the main goal is reproducibility and AI authoring. AI can reason about explicit SQL fixtures much more reliably than about layers of dynamic object factories.

### Recommendation for seed layout

Use a structure like:

- `db/migrations/`
- `db/seeds/base/`
- `db/seeds/scenarios/<scenario-name>.sql`
- generated baseline dump artifact keyed to the migration+seed state

This keeps schema evolution, canonical baseline state, and scenario-specific deltas separate.

## 5. Database version control beyond migrations

Migrations alone are not enough. A durable database version-control system should include:

### Canonical schema snapshot

Commit a generated **schema snapshot** in Git, preferably produced from the fully migrated database:

- `pg_dump --schema-only` is the simplest PostgreSQL-native option.
- Atlas schema export/inspection can also fill this role if Atlas is adopted.

Why keep it:

- makes drift visible in review
- gives humans and AI a "current truth" document
- helps detect when migration history and resulting schema diverge

### Query files as first-class versioned artifacts

If the platform adopts explicit SQL for reads/writes, the SQL query files are part of the database contract and should live in Git next to the application code.

That also improves AI performance because the system can reason over real queries rather than reverse-engineering ORM behavior.

### Seed assets under version control

Baseline seeds and scenario deltas should be versioned exactly like schema changes. They are part of the executable state contract for CI/E2E.

### Migration integrity and drift checks

If Atlas is used:

- keep `atlas.sum`
- run migration integrity/lint checks in CI
- fail the build on history drift or unsafe changes

If Atlas is not used:

- still run scratch-database apply in CI
- generate a schema-only snapshot after apply
- diff it against the committed canonical snapshot

### PostgreSQL-native objects treated as code

Functions, triggers, RLS policies, extensions, and views should be kept in explicit SQL and treated like code review artifacts. This is another place where SQL-first workflows are materially better than ORM-first ones.

## Final recommendation

For this FastAPI + PostgreSQL platform, I recommend:

1. **Primary migration model**
   - Keep migrations as **versioned SQL files in Git**.
   - Let AI draft SQL migrations, but require PR review of the exact SQL.
   - Use **Atlas** as the preferred companion tool for hashing, apply state, diff generation, and CI linting.

2. **Tooling stance**
   - Use Atlas primarily as a **SQL migration safety/control layer**, not as a reason to move the schema truth into ORM metadata.
   - If Atlas Pro is unacceptable, keep raw SQL migrations anyway and replace Atlas features with simpler CI checks plus schema snapshots.
   - Do **not** make Alembic the primary strategy unless the team explicitly chooses SQLAlchemy metadata as an architectural dependency.

3. **Data access**
   - Use **`psycopg` 3 + typed row factories + Pydantic/dataclass DTOs**.
   - Keep SQL explicit and close to the repository/query layer.
   - Do not adopt a heavyweight ORM as the center of the stack.

4. **E2E database strategy**
   - Build one migrated+seeded **`pg_dump -Fc` baseline artifact** per commit/CI run.
   - Restore once per Buildkite job.
   - Clone a template database per scenario for fast reset and strong isolation.

5. **Seeding**
   - Separate bootstrap/reference data, baseline test seed, and scenario delta seeds.
   - Prefer plain SQL/COPY fixtures over opaque seeder code.

6. **Prisma in 2026**
   - Prisma still adds value for **TypeScript-first** stacks because Prisma Client, TypedSQL, and newer config/runtime features are real improvements.
   - It does **not** add enough value to justify becoming the primary database stack for this Python-first platform.

If I reduce that to one sentence: **use PostgreSQL as PostgreSQL, keep migrations and seeds as SQL, use Atlas for safety if acceptable, and keep Python data access thin with `psycopg` rather than rebuilding a schema-centric ORM stack.**

## Sources

- Alembic autogenerate docs: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Atlas feature compatibility: https://atlasgo.io/features
- Atlas manual/versioned migrations: https://atlasgo.io/versioned/new
- Atlas CI/CD for versioned migrations: https://atlasgo.io/versioned/setup-cicd
- Atlas migration linting: https://atlasgo.io/versioned/lint
- Prisma Migrate overview: https://www.prisma.io/docs/orm/prisma-migrate/understanding-prisma-migrate/overview
- Prisma Migrate development and production workflow: https://www.prisma.io/docs/orm/prisma-migrate/workflows/development-and-production
- Prisma seeding: https://www.prisma.io/docs/orm/prisma-migrate/workflows/seeding
- Prisma TypedSQL: https://www.prisma.io/docs/orm/prisma-client/using-raw-sql/typedsql
- Prisma ORM v6.13.0 changelog (`prisma.config.ts`, TypedSQL locations, external tables, seed config): https://www.prisma.io/changelog/2025-07-30
- sqlc home: https://sqlc.dev/
- sqlc configuration reference: https://docs.sqlc.dev/en/latest/reference/config.html
- sqlc plugins guide: https://docs.sqlc.dev/en/latest/guides/plugins.html
- psycopg 3 row factories: https://www.psycopg.org/psycopg3/docs/advanced/rows.html
- PostgreSQL `CREATE DATABASE`: https://www.postgresql.org/docs/current/sql-createdatabase.html
- PostgreSQL `pg_dump`: https://www.postgresql.org/docs/current/app-pgdump.html
- PostgreSQL `pg_restore`: https://www.postgresql.org/docs/current/app-pgrestore.html
