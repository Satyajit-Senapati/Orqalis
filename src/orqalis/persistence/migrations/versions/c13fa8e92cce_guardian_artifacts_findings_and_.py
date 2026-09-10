"""guardian artifacts findings and delivery gates"""

import sqlalchemy as sa
from alembic import op

revision = "c13fa8e92cce"
down_revision = "29e512365451"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "git_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("tree_hash", sa.String(length=64), nullable=False),
        sa.Column("git_tree_sha", sa.String(length=64), nullable=False),
        sa.Column("commit_message", sa.Text(), nullable=False),
        sa.Column("commit_attached", sa.Boolean(), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("push_status", sa.String(length=32), nullable=False),
        sa.Column("remote", sa.String(length=255), nullable=True),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_git_deliveries_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_git_deliveries")),
        sa.UniqueConstraint("run_id", name=op.f("uq_git_deliveries_run_id")),
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("path_or_uri", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_artifacts_run_id_runs")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_artifacts_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
    )
    op.create_index(op.f("ix_artifacts_run_id"), "artifacts", ["run_id"], unique=False)
    op.create_table(
        "change_guard_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("tree_hash", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("checkpoint", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_change_guard_reports_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_change_guard_reports_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_change_guard_reports")),
    )
    op.create_index(
        op.f("ix_change_guard_reports_run_id"), "change_guard_reports", ["run_id"], unique=False
    )
    op.create_table(
        "final_validations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("goal_version_id", sa.Uuid(), nullable=False),
        sa.Column("tree_hash", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_final_validations_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_version_id"],
            ["goal_versions.id"],
            name=op.f("fk_final_validations_goal_version_id_goal_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_final_validations_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_final_validations")),
    )
    op.create_index(
        op.f("ix_final_validations_run_id"), "final_validations", ["run_id"], unique=False
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("criterion_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["acceptance_criteria.id"],
            name=op.f("fk_findings_criterion_id_acceptance_criteria"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_findings_run_id_runs")),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_findings_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
    )
    op.create_index(op.f("ix_findings_run_id"), "findings", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_findings_run_id"), table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_final_validations_run_id"), table_name="final_validations")
    op.drop_table("final_validations")
    op.drop_index(op.f("ix_change_guard_reports_run_id"), table_name="change_guard_reports")
    op.drop_table("change_guard_reports")
    op.drop_index(op.f("ix_artifacts_run_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_table("git_deliveries")
