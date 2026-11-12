"""

Revision ID: b7d19a6e2f40
Revises: cbbbe7571bfc
Create Date: 2026-11-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7d19a6e2f40"
down_revision = "cbbbe7571bfc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old records use percentage floats (for example 100.5000); the new
    # representation is percentage * 10000, matching maib_maichartachs.
    # The CASE also makes a retry safe if a previous SQLite batch migration
    # completed the data update before failing during the schema update.
    op.execute("""
        UPDATE maib_mairecords
        SET achievement = CASE
            WHEN achievement <= 202.0 THEN achievement * 10000
            ELSE achievement
        END
    """)
    with op.batch_alter_table("maib_mairecords", schema=None) as batch_op:
        batch_op.alter_column(
            "achievement",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using="achievement::integer",
        )


def downgrade() -> None:
    with op.batch_alter_table("maib_mairecords", schema=None) as batch_op:
        batch_op.alter_column(
            "achievement",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
            postgresql_using="achievement::double precision",
        )
    op.execute("UPDATE maib_mairecords SET achievement = achievement / 10000.0")
