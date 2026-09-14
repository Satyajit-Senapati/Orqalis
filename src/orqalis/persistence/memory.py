from uuid import UUID

from sqlalchemy import case, delete, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from orqalis.domain.errors import NotFoundError
from orqalis.domain.memory import (
    ArchitectureEntity,
    ArchitectureRelation,
    MemoryItem,
    MemoryMatch,
    MemorySource,
    ProjectSnapshot,
    RepositoryFile,
)
from orqalis.persistence.memory_models import (
    ArchitectureEntityRow,
    ArchitectureRelationRow,
    FileRow,
    MemoryRow,
    SnapshotRow,
    SourceRow,
)
from orqalis.persistence.models import ProjectRow


class SQLMemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_project(self, project_id: UUID) -> None:
        row = self.session.scalar(
            select(ProjectRow.id).where(ProjectRow.id == project_id).with_for_update()
        )
        if row is None:
            raise NotFoundError("Project not found")

    def latest_snapshot(self, project_id: UUID) -> ProjectSnapshot | None:
        row = self.session.scalar(
            select(SnapshotRow)
            .where(SnapshotRow.project_id == project_id)
            .order_by(SnapshotRow.created_at.desc())
            .limit(1)
        )
        return ProjectSnapshot.model_validate(row, from_attributes=True) if row else None

    def save_snapshot(self, snapshot: ProjectSnapshot) -> None:
        self.session.add(SnapshotRow(**snapshot.model_dump()))
        self.session.flush()

    def files(self, project_id: UUID) -> tuple[RepositoryFile, ...]:
        return tuple(
            RepositoryFile.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(FileRow).where(FileRow.project_id == project_id).order_by(FileRow.path)
            )
        )

    def current_file(self, project_id: UUID, path: str) -> RepositoryFile | None:
        row = self.session.scalar(
            select(FileRow).where(FileRow.project_id == project_id, FileRow.path == path)
        )
        return RepositoryFile.model_validate(row, from_attributes=True) if row else None

    def save_file(self, file: RepositoryFile) -> None:
        values = file.model_dump()
        statement = insert(FileRow).values(**values)
        self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["project_id", "path"],
                set_={
                    key: value for key, value in values.items() if key not in {"id", "created_at"}
                },
            )
        )

    def remove_file(self, project_id: UUID, path: str) -> None:
        self.session.execute(
            delete(FileRow).where(FileRow.project_id == project_id, FileRow.path == path)
        )
        ids = select(ArchitectureEntityRow.id).where(
            ArchitectureEntityRow.project_id == project_id, ArchitectureEntityRow.name == path
        )
        self.session.execute(
            delete(ArchitectureRelationRow).where(
                or_(
                    ArchitectureRelationRow.source_entity_id.in_(ids),
                    ArchitectureRelationRow.target_entity_id.in_(ids),
                )
            )
        )
        self.session.execute(delete(ArchitectureEntityRow).where(ArchitectureEntityRow.id.in_(ids)))

    def invalidate_path(self, project_id: UUID, path: str, replacement: UUID | None) -> int:
        ids = select(SourceRow.memory_item_id).where(SourceRow.source_ref == path)
        criteria = [
            MemoryRow.project_id == project_id,
            MemoryRow.id.in_(ids),
            MemoryRow.status == "active",
        ]
        if replacement:
            criteria.append(MemoryRow.id != replacement)
        affected = tuple(self.session.scalars(select(MemoryRow.id).where(*criteria)))
        self.session.execute(
            update(MemoryRow)
            .where(*criteria)
            .values(
                status="superseded" if replacement else "invalidated", superseded_by=replacement
            )
        )
        return len(affected)

    def add_item(
        self,
        item: MemoryItem,
        source: MemorySource,
        embedding: tuple[float, ...] | None,
        embedding_model: str | None,
    ) -> None:
        self.session.add(
            MemoryRow(
                **item.model_dump(),
                embedding=list(embedding) if embedding else None,
                embedding_model=embedding_model,
            )
        )
        self.session.flush()
        self.session.add(SourceRow(**source.model_dump()))
        self.session.flush()

    def missing_embeddings(
        self, project_id: UUID, embedding_model: str, limit: int = 100
    ) -> tuple[MemoryItem, ...]:
        return tuple(
            MemoryItem.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(MemoryRow)
                .where(
                    MemoryRow.project_id == project_id,
                    MemoryRow.status == "active",
                    MemoryRow.embedding_model == embedding_model,
                    MemoryRow.embedding.is_(None),
                )
                .order_by(MemoryRow.id)
                .limit(limit)
            )
        )

    def save_embedding(
        self,
        project_id: UUID,
        item_id: UUID,
        embedding: tuple[float, ...],
        embedding_model: str,
    ) -> None:
        self.session.execute(
            update(MemoryRow)
            .where(
                MemoryRow.project_id == project_id,
                MemoryRow.id == item_id,
                MemoryRow.status == "active",
                MemoryRow.embedding_model == embedding_model,
                MemoryRow.embedding.is_(None),
            )
            .values(embedding=list(embedding))
        )

    def attribute_commit(self, project_id: UUID, commit: str, run_id: UUID) -> None:
        self.session.execute(
            update(MemoryRow)
            .where(
                MemoryRow.project_id == project_id,
                MemoryRow.source_commit == commit,
                MemoryRow.introduced_by_run.is_(None),
            )
            .values(introduced_by_run=run_id)
        )

    def items_for_run(self, run_id: UUID) -> tuple[MemoryItem, ...]:
        return tuple(
            MemoryItem.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(MemoryRow)
                .where(MemoryRow.introduced_by_run == run_id)
                .order_by(MemoryRow.created_at, MemoryRow.id)
            )
        )

    def active_count(self, project_id: UUID) -> int:
        return (
            self.session.scalar(
                select(func.count())
                .select_from(MemoryRow)
                .where(MemoryRow.project_id == project_id, MemoryRow.status == "active")
            )
            or 0
        )

    def search(
        self,
        project_id: UUID,
        terms: tuple[str, ...],
        limit: int,
        embedding: tuple[float, ...] | None = None,
        embedding_model: str | None = None,
        excluded_ids: tuple[UUID, ...] = (),
    ) -> tuple[MemoryMatch, ...]:
        base = select(MemoryRow).where(
            MemoryRow.project_id == project_id,
            MemoryRow.status == "active",
            MemoryRow.id.not_in(excluded_ids),
        )
        filters = [
            or_(
                MemoryRow.title.icontains(term, autoescape=True),
                MemoryRow.content.icontains(term, autoescape=True),
            )
            for term in terms
        ]
        rank: ColumnElement[int] = literal(0)
        for predicate in filters:
            rank = rank + case((predicate, 1), else_=0)
        query = base.where(or_(*filters)) if filters else base
        candidates = {
            row.id: row
            for row in self.session.scalars(
                query.order_by(rank.desc(), MemoryRow.title, MemoryRow.id).limit(limit * 4)
            )
        }
        similarities: dict[UUID, float] = {}
        if embedding and embedding_model:
            distance = MemoryRow.embedding.cosine_distance(list(embedding))
            vector_query = (
                select(MemoryRow, distance.label("distance"))
                .where(
                    MemoryRow.project_id == project_id,
                    MemoryRow.status == "active",
                    MemoryRow.embedding_model == embedding_model,
                    MemoryRow.embedding.is_not(None),
                    func.vector_dims(MemoryRow.embedding) == len(embedding),
                    MemoryRow.id.not_in(excluded_ids),
                )
                .order_by(distance)
                .limit(limit)
            )
            for row, value in self.session.execute(vector_query):
                candidates[row.id] = row
                similarities[row.id] = max(0.0, 1.0 - float(value))
        matches = []
        for row in candidates.values():
            text = f"{row.title} {row.content}".lower()
            score = sum(term in text for term in terms) / max(1, len(terms))
            sources = tuple(
                MemorySource.model_validate(source, from_attributes=True)
                for source in self.session.scalars(
                    select(SourceRow)
                    .where(SourceRow.memory_item_id == row.id)
                    .order_by(SourceRow.source_ref)
                )
            )
            matches.append(
                MemoryMatch(
                    item=MemoryItem.model_validate(row, from_attributes=True),
                    sources=sources,
                    score=max(score, similarities.get(row.id, 0)),
                )
            )
        return tuple(sorted(matches, key=lambda match: (-match.score, match.item.title))[:limit])

    def save_entity(self, entity: ArchitectureEntity) -> None:
        self.session.execute(
            insert(ArchitectureEntityRow)
            .values(**entity.model_dump())
            .on_conflict_do_nothing(index_elements=["project_id", "name"])
        )

    def save_relation(self, relation: ArchitectureRelation) -> None:
        self.session.execute(
            insert(ArchitectureRelationRow)
            .values(**relation.model_dump())
            .on_conflict_do_nothing(
                index_elements=["source_entity_id", "relation_type", "target_entity_id"]
            )
        )

    def graph(
        self, project_id: UUID
    ) -> tuple[tuple[ArchitectureEntity, ...], tuple[ArchitectureRelation, ...]]:
        entities = tuple(
            ArchitectureEntity.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ArchitectureEntityRow)
                .where(ArchitectureEntityRow.project_id == project_id)
                .order_by(ArchitectureEntityRow.name)
            )
        )
        relations = tuple(
            ArchitectureRelation.model_validate(row, from_attributes=True)
            for row in self.session.scalars(
                select(ArchitectureRelationRow)
                .where(ArchitectureRelationRow.project_id == project_id)
                .order_by(ArchitectureRelationRow.id)
            )
        )
        return entities, relations
