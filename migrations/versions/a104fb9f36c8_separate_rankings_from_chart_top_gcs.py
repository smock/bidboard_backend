"""Separate rankings from chart (top gcs)

Revision ID: a104fb9f36c8
Revises: 35fde61523ae
Create Date: 2024-03-11 15:52:09.310831

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a104fb9f36c8'
down_revision: Union[str, None] = '35fde61523ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('gc_chart_rankings',
    sa.Column('id', sa.CHAR(32), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('gc_chart_id', sa.CHAR(32), nullable=False),
    sa.Column('metric', sa.String(length=100), nullable=False),
    sa.Column('dob_company_ids', sa.JSON(none_as_null=True), nullable=True),
    sa.Column('deltas', sa.JSON(none_as_null=True), nullable=True),
    sa.ForeignKeyConstraint(['gc_chart_id'], ['gc_charts.id'], name='fk_gc_chart_rankings_gc_charts_id_gc_chart_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('gc_chart_id', 'metric', name='uc_gc_chart_rankings_gc_chart_id_metric')
    )
    op.create_index(op.f('ix_gc_chart_rankings_created_at'), 'gc_chart_rankings', ['created_at'], unique=False)
    op.add_column('gc_charts', sa.Column('permits_rolled_up_at', sa.DateTime(), nullable=True))
    op.add_column('gc_charts', sa.Column('rankings_synced_dat', sa.DateTime(), nullable=True))
    op.drop_constraint('uc_gc_permit_charts', 'gc_charts', type_='unique')
    op.create_unique_constraint('uc_gc_permit_charts', 'gc_charts', ['start_date', 'end_date', 'borough', 'building_code'])
    op.drop_column('gc_charts', 'dob_company_ids')
    op.drop_column('gc_charts', 'is_complete')
    op.drop_column('gc_charts', 'deltas')
    op.drop_column('gc_charts', 'path')
    op.drop_column('gc_charts', 'metric')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('gc_charts', sa.Column('metric', sa.VARCHAR(length=100), autoincrement=False, nullable=False))
    op.add_column('gc_charts', sa.Column('path', sa.VARCHAR(length=500), autoincrement=False, nullable=True))
    op.add_column('gc_charts', sa.Column('deltas', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.add_column('gc_charts', sa.Column('is_complete', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.add_column('gc_charts', sa.Column('dob_company_ids', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
    op.drop_constraint('uc_gc_permit_charts', 'gc_charts', type_='unique')
    op.create_unique_constraint('uc_gc_permit_charts', 'gc_charts', ['metric', 'start_date', 'end_date', 'borough', 'building_code'])
    op.drop_column('gc_charts', 'rankings_synced_dat')
    op.drop_column('gc_charts', 'permits_rolled_up_at')
    op.drop_index(op.f('ix_gc_chart_rankings_created_at'), table_name='gc_chart_rankings')
    op.drop_table('gc_chart_rankings')
    # ### end Alembic commands ###
