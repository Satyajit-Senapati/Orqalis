"""versioned goals acceptance and evidence"""

import sqlalchemy as sa
from alembic import op

revision = "9d45acc139d7"
down_revision = "9be36332f594"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("target_branch", sa.String(length=255), nullable=False),
        sa.Column("base_commit", sa.String(length=64), nullable=False),
        sa.Column("current_goal_version_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("ui_phase", sa.String(length=32), nullable=False),
        sa.Column("repair_iteration", sa.Integer(), nullable=False),
        sa.Column("max_repair_iterations", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_runs_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index(op.f("ix_runs_project_id"), "runs", ["project_id"], unique=False)
    op.create_table(
        "goal_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("out_of_scope", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("definition_of_done", sa.JSON(), nullable=False),
        sa.Column("supersedes_goal_version_id", sa.Uuid(), nullable=True),
        sa.Column("revision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_goal_versions_run_id_runs")),
        sa.ForeignKeyConstraint(
            ["supersedes_goal_version_id"],
            ["goal_versions.id"],
            name=op.f("fk_goal_versions_supersedes_goal_version_id_goal_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal_versions")),
        sa.UniqueConstraint("run_id", "version", name=op.f("uq_goal_versions_run_id")),
    )
    op.create_index(op.f("ix_goal_versions_run_id"), "goal_versions", ["run_id"], unique=False)
    op.create_table(
        "acceptance_criteria",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("goal_version_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("validation_spec", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["goal_version_id"],
            ["goal_versions.id"],
            name=op.f("fk_acceptance_criteria_goal_version_id_goal_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acceptance_criteria")),
        sa.UniqueConstraint(
            "goal_version_id", "key", name=op.f("uq_acceptance_criteria_goal_version_id")
        ),
    )
    op.create_index(
        op.f("ix_acceptance_criteria_goal_version_id"),
        "acceptance_criteria",
        ["goal_version_id"],
        unique=False,
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_execution_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_ref", sa.Uuid(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"],
            ["acceptance_criteria.id"],
            name=op.f("fk_evidence_criterion_id_acceptance_criteria"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_evidence_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_criterion_id"), "evidence", ["criterion_id"], unique=False)
    op.create_index(op.f("ix_evidence_run_id"), "evidence", ["run_id"], unique=False)

    op.create_foreign_key(
        "fk_runs_current_goal_version_id_goal_versions",
        "runs",
        "goal_versions",
        ["current_goal_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_runs_current_goal_version_id_goal_versions", "runs", type_="foreignkey")
    op.drop_index(op.f("ix_evidence_run_id"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_criterion_id"), table_name="evidence")
    op.drop_table("evidence")
    op.drop_index(op.f("ix_acceptance_criteria_goal_version_id"), table_name="acceptance_criteria")
    op.drop_table("acceptance_criteria")
    op.drop_index(op.f("ix_goal_versions_run_id"), table_name="goal_versions")
    op.drop_table("goal_versions")
    op.drop_index(op.f("ix_runs_project_id"), table_name="runs")
    op.drop_table("runs")
