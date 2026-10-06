from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.core.agent import AgentState


@dataclass
class ProjectRecord:
    project_id: str
    repository_path: Path

    analysis: object | None = None
    changes: list[str] = field(default_factory=list)
    execution: object | None = None

    agent_state: AgentState = field(
        default_factory=AgentState
    )


class ProjectRepository:
    """In-memory project store for the MVP."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectRecord] = {}

    def create(self, repository_path: Path) -> ProjectRecord:
        project_id = str(uuid4())

        project = ProjectRecord(
            project_id=project_id,
            repository_path=repository_path,
        )

        self._projects[project_id] = project

        return project

    def get(self, project_id: str) -> ProjectRecord | None:
        return self._projects.get(project_id)

    def delete(self, project_id: str) -> bool:
        return self._projects.pop(
            project_id,
            None,
        ) is not None