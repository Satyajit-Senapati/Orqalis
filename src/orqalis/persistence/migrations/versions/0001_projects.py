"""Project identity foundation; immutable migration independent of live ORM metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("repo_uri", sa.String(2048), nullable=True),
        sa.Column("repo_root", sa.String(2048), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("repo_root", name="uq_projects_repo_root"),
    )


def downgrade() -> None:
    op.drop_table("projects")
