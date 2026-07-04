"""Refactor maib service models

Revision ID: 58124164bc13
Revises: 2f098106901e
Create Date: 2026-07-18 17:14:06.641126

"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58124164bc13'
down_revision = '2f098106901e'
branch_labels = None
depends_on = None


ASIA_SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
DEFAULT_DATETIME = datetime(1970, 11, 1, 0, 0, 0, tzinfo=ASIA_SHANGHAI)


def _unix_to_datetime(value: Any) -> datetime:
    if value is None:
        return DEFAULT_DATETIME
    if isinstance(value, datetime):
        return value

    timestamp = float(value)
    if timestamp <= 0:
        return DEFAULT_DATETIME
    return datetime.fromtimestamp(timestamp, ASIA_SHANGHAI)


def _datetime_to_unix(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    dt: datetime
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return 0
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ASIA_SHANGHAI)
    if dt <= DEFAULT_DATETIME:
        return 0
    return int(dt.timestamp())


def _replace_column_with_converted_values(
    table_name: str,
    pk_column: str,
    column_name: str,
    target_type: sa.types.TypeEngine[Any],
    converter: Callable[[Any], Any],
) -> None:
    conn = op.get_bind()
    tmp_column = f"{column_name}_migration_tmp"

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(sa.Column(tmp_column, target_type, nullable=True))

    rows = conn.execute(sa.text(f"SELECT {pk_column}, {column_name} FROM {table_name}")).mappings()
    updates = [
        {
            "pk_value": row[pk_column],
            "converted_value": converter(row[column_name]),
        }
        for row in rows
    ]
    if updates:
        stmt = sa.text(
            f"UPDATE {table_name} "
            f"SET {tmp_column} = :converted_value "
            f"WHERE {pk_column} = :pk_value"
        ).bindparams(sa.bindparam("converted_value", type_=target_type))
        conn.execute(stmt, updates)

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_column(column_name)

    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.alter_column(
            tmp_column,
            new_column_name=column_name,
            existing_type=target_type,
            existing_nullable=True,
            nullable=False,
        )


def upgrade() -> None:
    datetime_type = sa.DateTime(timezone=True)

    _replace_column_with_converted_values(
        "maib_maialiases",
        "id",
        "create_time",
        datetime_type,
        _unix_to_datetime,
    )
    _replace_column_with_converted_values(
        "maib_maichartachs",
        "id",
        "update_time",
        datetime_type,
        _unix_to_datetime,
    )

    with op.batch_alter_table('maib_maidatas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('jp_is_plate_required', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('cn_is_plate_required', sa.Boolean(), nullable=False, server_default=sa.true()))

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('jp_current_version', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('jp_dxra_b35_total', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('jp_dxra_b15_total', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('cn_current_version', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('cn_dxra_b35_total', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('cn_dxra_b15_total', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.alter_column(
            'jp_dxrating',
            new_column_name='jp_dxra_total',
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'jp_dxrating_b35_first',
            new_column_name='jp_dxra_b35_max',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxrating_b35_last',
            new_column_name='jp_dxra_b35_min',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxrating_b15_first',
            new_column_name='jp_dxra_b15_max',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxrating_b15_last',
            new_column_name='jp_dxra_b15_min',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxrating',
            new_column_name='cn_dxra_total',
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'cn_dxrating_b35_first',
            new_column_name='cn_dxra_b35_max',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxrating_b35_last',
            new_column_name='cn_dxra_b35_min',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxrating_b15_first',
            new_column_name='cn_dxra_b15_max',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxrating_b15_last',
            new_column_name='cn_dxra_b15_min',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )

    _replace_column_with_converted_values(
        "maib_maiusers",
        "user_id",
        "jp_update_time",
        datetime_type,
        _unix_to_datetime,
    )
    _replace_column_with_converted_values(
        "maib_maiusers",
        "user_id",
        "cn_update_time",
        datetime_type,
        _unix_to_datetime,
    )


def downgrade() -> None:
    integer_type = sa.Integer()

    _replace_column_with_converted_values(
        "maib_maiusers",
        "user_id",
        "cn_update_time",
        integer_type,
        _datetime_to_unix,
    )
    _replace_column_with_converted_values(
        "maib_maiusers",
        "user_id",
        "jp_update_time",
        integer_type,
        _datetime_to_unix,
    )

    with op.batch_alter_table('maib_maiusers', schema=None) as batch_op:
        batch_op.alter_column(
            'cn_dxra_b35_max',
            new_column_name='cn_dxrating_b35_first',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxra_total',
            new_column_name='jp_dxrating',
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'cn_dxra_b15_min',
            new_column_name='cn_dxrating_b15_last',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxra_b35_min',
            new_column_name='jp_dxrating_b35_last',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxra_b35_max',
            new_column_name='jp_dxrating_b35_first',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'jp_dxra_b15_max',
            new_column_name='jp_dxrating_b15_first',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxra_b15_max',
            new_column_name='cn_dxrating_b15_first',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxra_total',
            new_column_name='cn_dxrating',
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            'jp_dxra_b15_min',
            new_column_name='jp_dxrating_b15_last',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.alter_column(
            'cn_dxra_b35_min',
            new_column_name='cn_dxrating_b35_last',
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text('0'),
        )
        batch_op.drop_column('cn_dxra_b15_total')
        batch_op.drop_column('cn_dxra_b35_total')
        batch_op.drop_column('cn_current_version')
        batch_op.drop_column('jp_dxra_b15_total')
        batch_op.drop_column('jp_dxra_b35_total')
        batch_op.drop_column('jp_current_version')

    with op.batch_alter_table('maib_maidatas', schema=None) as batch_op:
        batch_op.drop_column('cn_is_plate_required')
        batch_op.drop_column('jp_is_plate_required')

    _replace_column_with_converted_values(
        "maib_maichartachs",
        "id",
        "update_time",
        integer_type,
        _datetime_to_unix,
    )
    _replace_column_with_converted_values(
        "maib_maialiases",
        "id",
        "create_time",
        integer_type,
        _datetime_to_unix,
    )
