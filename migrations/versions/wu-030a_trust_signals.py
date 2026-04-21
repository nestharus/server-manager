"""WU-030A trust signals."""

from __future__ import annotations

from alembic import op


revision = "wu_030a_trust_signals"
down_revision = "wu_037_ticket_sla_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE trust_signals (
            id UUID PRIMARY KEY,
            member_id UUID NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
            signal_type TEXT NOT NULL,
            scope_kind TEXT NOT NULL,
            scope_id TEXT NULL,
            scope JSONB NOT NULL,
            value JSONB NOT NULL,
            source_actor_kind TEXT NOT NULL,
            source_actor_id TEXT NOT NULL,
            observed_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT trust_signals_scope_kind_valid
                CHECK (scope_kind IN ('global', 'chapter', 'member')),
            CONSTRAINT trust_signals_scope_id_shape
                CHECK (
                    (scope_kind = 'global' AND scope_id IS NULL)
                    OR (scope_kind IN ('chapter', 'member') AND scope_id IS NOT NULL)
                ),
            CONSTRAINT trust_signals_source_actor_kind_valid
                CHECK (source_actor_kind IN ('user', 'service')),
            CONSTRAINT trust_signals_signal_type_not_blank
                CHECK (char_length(signal_type) > 0),
            CONSTRAINT trust_signals_source_actor_id_not_blank
                CHECK (char_length(source_actor_id) > 0),
            CONSTRAINT trust_signals_scope_is_object
                CHECK (jsonb_typeof(scope) = 'object'),
            CONSTRAINT trust_signals_scope_kind_matches_json
                CHECK (scope->>'scope_kind' = scope_kind),
            CONSTRAINT trust_signals_scope_id_matches_json
                CHECK (
                    (scope_kind = 'global' AND NOT (scope ? 'scope_id'))
                    OR (scope_kind IN ('chapter', 'member') AND scope->>'scope_id' = scope_id)
                ),
            CONSTRAINT trust_signals_value_is_object
                CHECK (jsonb_typeof(value) = 'object'),
            CONSTRAINT trust_signals_value_has_schema_version
                CHECK (
                    value ? 'schema_version'
                    AND jsonb_typeof(value->'schema_version') = 'number'
                ),
            CONSTRAINT trust_signals_expiry_after_observed
                CHECK (expires_at IS NULL OR expires_at > observed_at)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_signals__member_created
            ON trust_signals (member_id, created_at DESC, id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_signals__member_type_observed
            ON trust_signals (member_id, signal_type, observed_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_signals__scope
            ON trust_signals (scope_kind, scope_id)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_signals__value_gin
            ON trust_signals USING GIN (value)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_signals__member_expires
            ON trust_signals (member_id, expires_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_trust_signals__member_expires")
    op.execute("DROP INDEX ix_trust_signals__value_gin")
    op.execute("DROP INDEX ix_trust_signals__scope")
    op.execute("DROP INDEX ix_trust_signals__member_type_observed")
    op.execute("DROP INDEX ix_trust_signals__member_created")
    op.execute("DROP TABLE trust_signals")

