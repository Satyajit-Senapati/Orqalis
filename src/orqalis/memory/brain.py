from collections.abc import Callable
from uuid import UUID

from orqalis.core.ports import ProjectUnitOfWork
from orqalis.domain.errors import NotFoundError, PolicyDeniedError
from orqalis.domain.memory import ProjectBrain
from orqalis.memory.service import MemoryService

_DEFAULT_BRAIN_QUERY = (
    "project product architecture technology conventions domain workflows testing "
    "pitfalls module decision task history"
)


class ProjectBrainService:
    def __init__(self, factory: Callable[[], ProjectUnitOfWork], memory: MemoryService) -> None:
        self.factory, self.memory = factory, memory

    def get(self, project_id: UUID, query: str = "", run_id: UUID | None = None) -> ProjectBrain:
        with self.factory() as uow:
            project = uow.projects.get(project_id)
            if project is None:
                raise NotFoundError("Project not found")
            inspected_project = project
            if run_id:
                run = uow.runs.get(run_id)
                if run is None or run.project_id != project_id:
                    raise PolicyDeniedError("Run does not belong to this project")
                workspace = uow.execution.workspace(run_id)
                if workspace:
                    inspected_project = project.model_copy(update={"repo_root": workspace.path})
        # The stable Brain graph shape remains a projection of the typed repository
        # graph. The ContextPack is the authority for ranked knowledge and freshness;
        # it contains curated memory, graph context, and related Task Capsules.
        entities, relations = self.memory.graph(project)
        context = self.memory.context(
            inspected_project,
            query if query.strip() else _DEFAULT_BRAIN_QUERY,
        )
        return ProjectBrain(
            project_id=project_id,
            inspected_root=inspected_project.repo_root,
            query=query,
            freshness=context.freshness,
            matches=context.items,
            entities=entities,
            relations=relations,
        )
