from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from orqalis.persistence.models import Base


class SnapshotRow(Base):
    __tablename__ = "project_snapshots"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    indexed_commit_sha: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    repo_fingerprint: Mapped[str] = mapped_column(String(64))
    files_scanned: Mapped[int] = mapped_column(Integer)
    invalidations: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FileRow(Base):
    __tablename__ = "repository_files"
    __table_args__ = (UniqueConstraint("project_id", "path"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    path: Mapped[str] = mapped_column(String(2048))
    language: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(64))
    content_hash: Mapped[str] = mapped_column(String(64))
    last_seen_commit: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MemoryRow(Base):
    __tablename__ = "project_memory"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(2048))
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    source_commit: Mapped[str] = mapped_column(String(64))
    introduced_by_run: Mapped[UUID | None] = mapped_column(Uuid)
    last_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[UUID | None] = mapped_column(ForeignKey("project_memory.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None] = mapped_column(String(255))


class SourceRow(Base):
    __tablename__ = "memory_sources"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    memory_item_id: Mapped[UUID] = mapped_column(ForeignKey("project_memory.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(2048), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    commit_sha: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchitectureEntityRow(Base):
    __tablename__ = "architecture_entities"
    __table_args__ = (UniqueConstraint("project_id", "name"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(2048))
    source_refs: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArchitectureRelationRow(Base):
    __tablename__ = "architecture_relations"
    __table_args__ = (UniqueConstraint("source_entity_id", "relation_type", "target_entity_id"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    source_entity_id: Mapped[UUID] = mapped_column(ForeignKey("architecture_entities.id"))
    relation_type: Mapped[str] = mapped_column(String(64))
    target_entity_id: Mapped[UUID] = mapped_column(ForeignKey("architecture_entities.id"))
    confidence: Mapped[float] = mapped_column(Float)
    source_refs: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
