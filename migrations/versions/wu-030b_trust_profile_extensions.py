"""WU-030B trust profile recompute metadata."""

from __future__ import annotations

from alembic import op


revision = "wu_030b_trust_profile_extensions"
down_revision = "wu_030a_trust_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE policy_versions
        SET policy_type = 'trust_computation'
        WHERE policy_type = 'trust'
          AND id IN (
              SELECT policy_version_id
              FROM trust_profiles
          )
        """
    )
    op.execute(
        """
        ALTER TABLE trust_profiles
            ADD COLUMN config_version BIGINT,
            ADD COLUMN computed_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        UPDATE trust_profiles AS tp
        SET config_version = pv.version_number,
            computed_at = tp.updated_at
        FROM policy_versions AS pv
        WHERE pv.id = tp.policy_version_id
        """
    )
    op.execute(
        """
        ALTER TABLE trust_profiles
            ALTER COLUMN config_version SET NOT NULL,
            ALTER COLUMN computed_at SET DEFAULT CURRENT_TIMESTAMP,
            ALTER COLUMN computed_at SET NOT NULL,
            ADD CONSTRAINT trust_profiles_config_version_positive
                CHECK (config_version > 0)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_profiles__config_version
            ON trust_profiles (config_version)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_trust_profiles__config_version")
    op.execute(
        """
        ALTER TABLE trust_profiles
            DROP CONSTRAINT trust_profiles_config_version_positive,
            DROP COLUMN computed_at,
            DROP COLUMN config_version
        """
    )
    op.execute(
        """
        UPDATE policy_versions
        SET policy_type = 'trust'
        WHERE policy_type = 'trust_computation'
          AND id IN (
              SELECT policy_version_id
              FROM trust_profiles
          )
        """
    )

