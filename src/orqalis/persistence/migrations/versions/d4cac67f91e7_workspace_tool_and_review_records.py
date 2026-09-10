"""workspace tool and review records"""

import sqlalchemy as sa
from alembic import op

revision = "d4cac67f91e7"
down_revision = "485d249a316d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_workspaces",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_workspaces_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_run_workspaces")),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("goal_version_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("tree_hash", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_reviews_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_version_id"],
            ["goal_versions.id"],
            name=op.f("fk_reviews_goal_version_id_goal_versions"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_reviews_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
    )
    op.create_index(op.f("ix_reviews_run_id"), "reviews", ["run_id"], unique=False)
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("task_execution_id", sa.Uuid(), nullable=False),
        sa.Column("actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("provider_invocation_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.String(length=255), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_tool_invocations_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["provider_invocation_id"],
            ["provider_executions.id"],
            name=op.f("fk_tool_invocations_provider_invocation_id_provider_executions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_tool_invocations_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["task_execution_id"],
            ["task_executions.id"],
            name=op.f("fk_tool_invocations_task_execution_id_task_executions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_invocations")),
        sa.UniqueConstraint(
            "provider_invocation_id",
            "call_id",
            name=op.f("uq_tool_invocations_provider_invocation_id"),
        ),
    )
    op.create_index(
        op.f("ix_tool_invocations_run_id"), "tool_invocations", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_tool_invocations_task_execution_id"),
        "tool_invocations",
        ["task_execution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_invocations_task_execution_id"), table_name="tool_invocations")
    op.drop_index(op.f("ix_tool_invocations_run_id"), table_name="tool_invocations")
    op.drop_table("tool_invocations")
    op.drop_index(op.f("ix_reviews_run_id"), table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("run_workspaces")
