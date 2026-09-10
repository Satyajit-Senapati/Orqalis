"""stable task membership across plan revisions"""

import sqlalchemy as sa
from alembic import op

revision = "29e512365451"
down_revision = "d4cac67f91e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_tasks",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_plan_tasks_plan_id_plans")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_plan_tasks_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("plan_id", "task_id", name=op.f("pk_plan_tasks")),
    )
    op.execute("""
        INSERT INTO plan_tasks (plan_id, task_id)
        SELECT plans.id, tasks.id FROM tasks
        JOIN plans ON plans.run_id = tasks.run_id AND plans.version = tasks.plan_version
    """)


def downgrade() -> None:
    op.drop_table("plan_tasks")
