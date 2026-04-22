"""WU-027 narrow permission_intent scope kinds to global|chapter."""

from __future__ import annotations

from alembic import op


revision = "wu_027_perm_intent_refinements"
down_revision = "wu_035_application_interview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM permission_intents WHERE scope_kind = 'member'
            ) THEN
                RAISE EXCEPTION
                    'SLICE-014 D1: permission_intents contains scope_kind=member '
                    'rows; forward migration refuses to narrow scope.';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint(
        "permission_intents_scope_kind_valid",
        "permission_intents",
        type_="check",
    )
    op.create_check_constraint(
        "permission_intents_scope_kind_valid",
        "permission_intents",
        "scope_kind IN ('global', 'chapter')",
    )
    op.create_check_constraint(
        "permission_intents_scope_shape_valid",
        "permission_intents",
        "(scope_kind = 'global' AND scope_id IS NULL) "
        "OR (scope_kind = 'chapter' AND scope_id IS NOT NULL)",
    )


def downgrade() -> None:
    # No-op per AGENTS.md Live Server Principle: widening the scope
    # constraint after narrowing would silently re-admit member rows a
    # running server cannot reconstruct. Reverts are explicit operator
    # actions, not migration responsibilities.
    pass
