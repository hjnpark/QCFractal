"""Add MOTD

Revision ID: 9c91ede09098
Revises: 301bec558dea
Create Date: 2022-09-08 11:02:28.976308

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9c91ede09098"
down_revision = "301bec558dea"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "motd",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("motd", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("motd")
    # ### end Alembic commands ###