"""provider invocation records"""

import sqlalchemy as sa
from alembic import op

revision = "485d249a316d"
down_revision = "77fd51b32c12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("task_execution_id", sa.Uuid(), nullable=False),
        sa.Column("actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_provider_executions_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_provider_executions_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["task_execution_id"],
            ["task_executions.id"],
            name=op.f("fk_provider_executions_task_execution_id_task_executions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_executions")),
        sa.UniqueConstraint(
            "run_id", "idempotency_key", name=op.f("uq_provider_executions_run_id")
        ),
    )
    op.create_index(
        op.f("ix_provider_executions_actor_session_id"),
        "provider_executions",
        ["actor_session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_executions_run_id"), "provider_executions", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_provider_executions_task_execution_id"),
        "provider_executions",
        ["task_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_provider_executions_task_execution_id"), table_name="provider_executions"
    )
    op.drop_index(op.f("ix_provider_executions_run_id"), table_name="provider_executions")
    op.drop_index(op.f("ix_provider_executions_actor_session_id"), table_name="provider_executions")
    op.drop_table("provider_executions")
