"""rename base dataset extra

Revision ID: 21e29b68cbd5
Revises: b9b7b6926b8b
Create Date: 2022-05-22 10:21:59.093555

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '21e29b68cbd5'
down_revision = 'b9b7b6926b8b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('base_dataset', 'extra', new_column_name='extras')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('base_dataset', 'extras', new_column_name='extra')
    # ### end Alembic commands ###
