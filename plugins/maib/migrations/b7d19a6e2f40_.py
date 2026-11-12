"""

Revision ID: b7d19a6e2f40
Revises: 9d1c4a7e2b60
Create Date: 2026-11-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7d19a6e2f40"
down_revision = "9d1c4a7e2b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Old records use percentage floats (for example 100.5000); the new
    # representation is percentage * 10000, matching maib_maichartachs.
    # ROUND avoids truncating float error (0.0003 * 10000 -> 2.9999999999999996),
    # and CAST keeps the value INTEGER in SQLite's dynamic typing.
    #
    # Idempotency: only convert when the whole table still looks like
    # percentages. A per-row `achievement <= 202.0` guard is not enough --
    # a converted value such as 3 (= 0.0003%) would be multiplied again on
    # retry. Checking the table maximum makes the retry a no-op.
    max_ach = op.get_bind().execute(
        sa.text("SELECT MAX(achievement) FROM maib_mairecords")
    ).scalar()
    if max_ach is None or max_ach <= 202.0:
        op.execute("""
            UPDATE maib_mairecords
            SET achievement = CAST(ROUND(achievement * 10000) AS INTEGER)
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
