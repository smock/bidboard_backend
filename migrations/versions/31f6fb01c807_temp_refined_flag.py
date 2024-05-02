"""temp refined flag

Revision ID: 31f6fb01c807
Revises: 1b2f35970d05
Create Date: 2024-04-29 11:23:25.458110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31f6fb01c807'
down_revision: Union[str, None] = '1b2f35970d05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('unique_image_annotations', sa.Column('refined', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('unique_image_annotations', 'refined')
    # ### end Alembic commands ###
