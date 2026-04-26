# INIT-113 Risk: Scope

Rating: **LOW**

The proposal stays inside packaging and local deployment. It does not add auth,
tenant isolation, observability, new application features, or Discord-visible
behavior. The only CI change is additive: app image build and static validation
steps reuse the INIT-109 local pipeline structure.

The Alembic job is in scope because the existing codebase already uses
Alembic and the API readiness contract requires `alembic_version`.
Replacing the migration system with Atlas-native SQL would be a separate
schema-management initiative.
