"""finalize migration of properties

Revision ID: 5a98e27e4c10
Revises: 95e84c316d4d
Create Date: 2023-03-03 14:57:04.765823

"""
import numpy as np
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import table, column

from qcfractal.db_socket.column_types import MsgpackExt

# revision identifiers, used by Alembic.
revision = "5a98e27e4c10"
down_revision = "95e84c316d4d"
branch_labels = None
depends_on = None


def convert_numpy(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [convert_numpy(v) for v in obj]
    elif isinstance(obj, np.ndarray):
        if obj.shape:
            return obj.ravel().tolist()
        else:
            return obj.tolist()
    else:
        return obj


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    base_table = table(
        "base_record",
        column("id", sa.Integer),
        column("record_type", sa.String),
        column("extras", MsgpackExt),
        column("new_extras", postgresql.JSONB),
        column("new_properties", postgresql.JSONB),
    )

    singlepoint_table = table(
        "singlepoint_record",
        column("id", sa.Integer),
        column("properties", postgresql.JSONB),
        column("return_result", MsgpackExt),
    )

    conn = op.get_bind()
    session = Session(conn)

    # Find records that haven't been migrated
    # Migrations should always set new_extras to something
    base_records = session.query(base_table).where(base_table.c.new_extras.is_(None)).yield_per(200)

    for br in base_records:
        # Find singlepoint rec if it exists
        new_properties = {}

        # Move return_result and properties from singlepoint into base record propertiesAnd return result
        if br.record_type == "singlepoint":
            sp_rec = session.query(singlepoint_table).where(singlepoint_table.c.id == br.id).one()
            if sp_rec.return_result is not None:
                new_properties["return_result"] = convert_numpy(sp_rec.return_result)
            if sp_rec.properties is not None:
                new_properties.update(sp_rec.properties)

        # convert any numpy objects in extras
        extras = convert_numpy(br.extras)

        # Add qcvars from extras (and remove from extras)
        if extras is not None:
            qcvars = extras.pop("qcvars", {})
            if qcvars:
                new_properties.update({k.lower(): v for k, v in qcvars.items()})

        session.execute(
            sa.update(base_table)
            .values(extras=None, new_extras=extras, new_properties=new_properties)
            .where(base_table.c.id == br.id)
        )

    session.commit()

    op.drop_column("base_record", "extras")
    op.drop_column("singlepoint_record", "return_result")
    op.drop_column("singlepoint_record", "properties")
    op.alter_column("base_record", "new_extras", new_column_name="extras")
    op.alter_column("base_record", "new_properties", new_column_name="properties")

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    raise RuntimeError("CANNOT DOWNGRADE")
    # ### end Alembic commands ###
