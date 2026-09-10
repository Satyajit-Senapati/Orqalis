from collections.abc import Callable
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.memory import ProjectBrain
from orqalis.memory.service import MemoryService


class ProjectBrainService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], memory: MemoryService) -> None:
        self.factory, self.memory = factory, memory

    def get(self, project_id: UUID, query: str = "", run_id: UUID | None = None) -> ProjectBrain:
        with self.factory() as uow:
            project = uow.projects.get(project_id)
            if project is None:
                raise NotFoundError("Project not found")
            if run_id:
                run = uow.runs.get(run_id)
                if run is None or run.project_id != project_id:
                    raise PolicyDeniedError("Run does not belong to this project")
                workspace = uow.execution.workspace(run_id)
                if workspace:
                    project = project.model_copy(update={"repo_root": workspace.path})
        matches = self.memory.search(project, query, 100)
        entities, relations = self.memory.graph(project)
        return ProjectBrain(
            project_id=project_id,
            inspected_root=project.repo_root,
            query=query,
            freshness=self.memory.health(project),
            matches=matches,
            entities=entities,
            relations=relations,
        )
