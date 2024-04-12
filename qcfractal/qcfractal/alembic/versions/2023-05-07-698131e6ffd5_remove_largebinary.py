"""remove largebinary

Revision ID: 698131e6ffd5
Revises: 363c647d7840
Create Date: 2023-05-07 11:24:42.527020

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "698131e6ffd5"
down_revision = "363c647d7840"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    # We assume no service subtask records for this migration
    conn = op.get_bind()
    r = conn.execute(sa.text("SELECT COUNT(*) FROM service_subtask_record"))
    n_subtasks = r.scalar_one()

    if n_subtasks > 0:
        raise RuntimeError(f"Cannot upgrade - there are {n_subtasks} existing service subtask records")

    # New columns in service_subtask_record are just plain JSON
    op.add_column("service_subtask_record", sa.Column("function_kwargs", sa.JSON(), nullable=False))
    op.add_column("service_subtask_record", sa.Column("results", sa.JSON(), nullable=True))

    # Remove old columns/indexes of service_subtask_record
    op.drop_index("ix_service_subtask_record_function_kwargs_lb_id", table_name="service_subtask_record")
    op.drop_index("ix_service_subtask_record_results_lb_id", table_name="service_subtask_record")
    op.drop_constraint(
        "service_subtask_record_function_kwargs_lb_id_fkey", "service_subtask_record", type_="foreignkey"
    )
    op.drop_constraint("service_subtask_record_results_lb_id_fkey", "service_subtask_record", type_="foreignkey")
    op.drop_column("service_subtask_record", "results_lb_id")
    op.drop_column("service_subtask_record", "function_kwargs_lb_id")

    # Now the task queue
    op.add_column("task_queue", sa.Column("function_kwargs_compressed", sa.LargeBinary(), nullable=True))
    op.drop_index("ix_task_queue_function_kwargs_lb_id", table_name="task_queue")
    op.drop_constraint("task_queue_function_kwargs_lb_id_fkey", "task_queue", type_="foreignkey")
    op.drop_column("task_queue", "function_kwargs_lb_id")

    # Remove the function from existing tasks. They will be autogenerated
    op.execute(sa.text("UPDATE task_queue SET function = NULL"))

    op.drop_table("largebinary_store")

    # Drop various functions and triggers
    op.execute(sa.text('drop trigger if exists "qca_service_subtask_delete_lb_tr" on "service_subtask_record";'))
    op.execute(sa.text('drop trigger if exists "qca_task_queue_delete_lb_tr" on "task_queue";'))
    op.execute(sa.text('drop function if exists "qca_largebinary_base_delete";'))
    op.execute(sa.text('drop function if exists "qca_service_subtask_delete_lb";'))
    op.execute(sa.text('drop function if exists "qca_task_queue_delete_lb";'))

    # ### end Alembic commands ###


def downgrade():
    raise RuntimeError("Cannot downgrade")
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("task_queue", sa.Column("function_kwargs_lb_id", sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(
        "task_queue_function_kwargs_lb_id_fkey", "task_queue", "largebinary_store", ["function_kwargs_lb_id"], ["id"]
    )
    op.create_index("ix_task_queue_function_kwargs_lb_id", "task_queue", ["function_kwargs_lb_id"], unique=False)
    op.drop_column("task_queue", "function_kwargs_compressed")
    op.add_column(
        "service_subtask_record", sa.Column("function_kwargs_lb_id", sa.INTEGER(), autoincrement=False, nullable=True)
    )
    op.add_column(
        "service_subtask_record", sa.Column("results_lb_id", sa.INTEGER(), autoincrement=False, nullable=True)
    )
    op.create_foreign_key(
        "service_subtask_record_results_lb_id_fkey",
        "service_subtask_record",
        "largebinary_store",
        ["results_lb_id"],
        ["id"],
    )
    op.create_foreign_key(
        "service_subtask_record_function_kwargs_lb_id_fkey",
        "service_subtask_record",
        "largebinary_store",
        ["function_kwargs_lb_id"],
        ["id"],
    )
    op.create_index(
        "ix_service_subtask_record_results_lb_id", "service_subtask_record", ["results_lb_id"], unique=False
    )
    op.create_index(
        "ix_service_subtask_record_function_kwargs_lb_id",
        "service_subtask_record",
        ["function_kwargs_lb_id"],
        unique=False,
    )
    op.drop_column("service_subtask_record", "results")
    op.drop_column("service_subtask_record", "function_kwargs")
    op.create_table(
        "largebinary_store",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("size", sa.BIGINT(), autoincrement=False, nullable=False),
        sa.Column("checksum", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column(
            "compression_type",
            postgresql.ENUM("none", "lzma", "zstd", name="compressionenum"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("data_local", postgresql.BYTEA(), autoincrement=False, nullable=False),
        sa.Column("largebinary_type", sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id", name="largebinary_store_pkey"),
    )
    # ### end Alembic commands ###