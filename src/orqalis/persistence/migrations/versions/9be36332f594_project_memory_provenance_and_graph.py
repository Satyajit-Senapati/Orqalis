"""project memory provenance and graph"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "9be36332f594"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "architecture_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=2048), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_architecture_entities_project_id_projects"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_architecture_entities")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_architecture_entities_project_id")),
    )
    op.create_index(
        op.f("ix_architecture_entities_project_id"),
        "architecture_entities",
        ["project_id"],
        unique=False,
    )
    op.create_table(
        "project_memory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=2048), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("introduced_by_run", sa.Uuid(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("embedding_model", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_memory_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["project_memory.id"],
            name=op.f("fk_project_memory_superseded_by_project_memory"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_memory")),
    )
    op.create_index(
        op.f("ix_project_memory_project_id"), "project_memory", ["project_id"], unique=False
    )
    op.create_index(op.f("ix_project_memory_status"), "project_memory", ["status"], unique=False)
    op.create_table(
        "project_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("indexed_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("repo_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("files_scanned", sa.Integer(), nullable=False),
        sa.Column("invalidations", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_snapshots_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_snapshots")),
    )
    op.create_index(
        op.f("ix_project_snapshots_project_id"), "project_snapshots", ["project_id"], unique=False
    )
    op.create_table(
        "repository_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("last_seen_commit", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_repository_files_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repository_files")),
        sa.UniqueConstraint("project_id", "path", name=op.f("uq_repository_files_project_id")),
    )
    op.create_index(
        op.f("ix_repository_files_project_id"), "repository_files", ["project_id"], unique=False
    )
    op.create_table(
        "architecture_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_architecture_relations_project_id_projects"),
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["architecture_entities.id"],
            name=op.f("fk_architecture_relations_source_entity_id_architecture_entities"),
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["architecture_entities.id"],
            name=op.f("fk_architecture_relations_target_entity_id_architecture_entities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_architecture_relations")),
        sa.UniqueConstraint(
            "source_entity_id",
            "relation_type",
            "target_entity_id",
            name=op.f("uq_architecture_relations_source_entity_id"),
        ),
    )
    op.create_index(
        op.f("ix_architecture_relations_project_id"),
        "architecture_relations",
        ["project_id"],
        unique=False,
    )
    op.create_table(
        "memory_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("memory_item_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=2048), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["memory_item_id"],
            ["project_memory.id"],
            name=op.f("fk_memory_sources_memory_item_id_project_memory"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_sources")),
    )
    op.create_index(
        op.f("ix_memory_sources_memory_item_id"), "memory_sources", ["memory_item_id"], unique=False
    )
    op.create_index(
        op.f("ix_memory_sources_source_ref"), "memory_sources", ["source_ref"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_sources_source_ref"), table_name="memory_sources")
    op.drop_index(op.f("ix_memory_sources_memory_item_id"), table_name="memory_sources")
    op.drop_table("memory_sources")
    op.drop_index(op.f("ix_architecture_relations_project_id"), table_name="architecture_relations")
    op.drop_table("architecture_relations")
    op.drop_index(op.f("ix_repository_files_project_id"), table_name="repository_files")
    op.drop_table("repository_files")
    op.drop_index(op.f("ix_project_snapshots_project_id"), table_name="project_snapshots")
    op.drop_table("project_snapshots")
    op.drop_index(op.f("ix_project_memory_status"), table_name="project_memory")
    op.drop_index(op.f("ix_project_memory_project_id"), table_name="project_memory")
    op.drop_table("project_memory")
    op.drop_index(op.f("ix_architecture_entities_project_id"), table_name="architecture_entities")
    op.drop_table("architecture_entities")
