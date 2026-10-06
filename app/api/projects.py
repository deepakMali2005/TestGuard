from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AgentStateResponse,
    Analysis,
    ApplyRequest,
    CreateProjectRequest,
    CreateProjectResponse,
    Report,
)
from app.core.orchestrator import TestGuardOrchestrator
from app.storage.repository import ProjectRepository


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)

repository = ProjectRepository()


def get_project_or_404(project_id: str):
    project = repository.get(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    return project


@router.post(
    "",
    response_model=CreateProjectResponse,
)
def create_project(
    request: CreateProjectRequest,
):
    repository_path = Path(
        request.repository_path
    ).resolve()

    if not repository_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Repository path does not exist.",
        )

    if not repository_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Repository path is not a directory.",
        )

    project = repository.create(
        repository_path
    )

    return CreateProjectResponse(
        project_id=project.project_id,
        repository_path=str(
            project.repository_path
        ),
        status="CREATED",
    )


@router.post(
    "/{project_id}/analyze",
    response_model=Analysis,
)
def analyze_project(project_id: str):
    project = get_project_or_404(project_id)

    try:
        return TestGuardOrchestrator(
            project
        ).analyze()

    except (
        FileNotFoundError,
        NotADirectoryError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/analysis",
    response_model=Analysis,
)
def get_analysis(project_id: str):
    project = get_project_or_404(project_id)

    if project.analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Project has not been analyzed yet.",
        )

    return project.analysis


@router.post(
    "/{project_id}/apply",
)
def apply_changes(
    project_id: str,
    request: ApplyRequest,
):
    project = get_project_or_404(project_id)

    orchestrator = TestGuardOrchestrator(
        project
    )

    if not request.approved:
        orchestrator.reject_changes()

        return {
            "status": "REJECTED",
            "message": (
                "Proposed repository changes "
                "were not approved."
            ),
        }

    try:
        changes = orchestrator.apply_changes()

        return {
            "status": "APPLIED",
            "changes": changes,
        }

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/run",
)
def run_tests(project_id: str):
    project = get_project_or_404(project_id)

    try:
        return TestGuardOrchestrator(
            project
        ).run_tests()

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/report",
    response_model=Report,
)
def get_report(project_id: str):
    project = get_project_or_404(project_id)

    try:
        return TestGuardOrchestrator(
            project
        ).report()

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/agent",
    response_model=AgentStateResponse,
)
def agent_step(project_id: str):
    project = get_project_or_404(project_id)

    state = project.agent_state

    return AgentStateResponse(
        status=state.status,
        iteration=state.iteration,
        max_iterations=state.max_iterations,
        awaiting_approval=state.awaiting_approval,
        steps=[
            {
                "step": step.step,
                "action": step.action,
                "observation": step.observation,
                "reasoning": step.reasoning,
                "next_action": step.next_action,
            }
            for step in state.steps
        ],
    )


@router.get(
    "/{project_id}/agent",
    response_model=AgentStateResponse,
)
def get_agent_state(project_id: str):
    project = get_project_or_404(project_id)

    state = project.agent_state

    return AgentStateResponse(
        status=state.status,
        iteration=state.iteration,
        max_iterations=state.max_iterations,
        awaiting_approval=state.awaiting_approval,
        steps=[
            {
                "step": step.step,
                "action": step.action,
                "observation": step.observation,
                "reasoning": step.reasoning,
                "next_action": step.next_action,
            }
            for step in state.steps
        ],
    )