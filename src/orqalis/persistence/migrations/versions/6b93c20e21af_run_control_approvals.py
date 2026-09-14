"""Persist per-run control policy and version-bound operator decisions."""

import sqlalchemy as sa
from alembic import op

revision = "6b93c20e21af"
down_revision = "c13fa8e92cce"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_control_policies",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("gates", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_run_control_policies_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_run_control_policies")),
    )
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("subject_version", sa.Integer(), nullable=False),
        sa.Column("subject_digest", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_approval_requests_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
        sa.UniqueConstraint(
            "run_id", "stage", "subject_version", "subject_digest", name="uq_approval_subject"
        ),
    )
    op.create_index(op.f("ix_approval_requests_run_id"), "approval_requests", ["run_id"])
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["approval_requests.id"],
            name=op.f("fk_approval_decisions_request_id_approval_requests"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_decisions")),
        sa.UniqueConstraint("request_id", name=op.f("uq_approval_decisions_request_id")),
    )


def downgrade() -> None:
    op.drop_table("approval_decisions")
    op.drop_index(op.f("ix_approval_requests_run_id"), table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_table("run_control_policies")
