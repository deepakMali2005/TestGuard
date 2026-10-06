from typing import Any, Literal

from pydantic import BaseModel, Field


Decision = Literal["TRUSTED", "REVIEW", "REJECT"]


class CreateProjectRequest(BaseModel):
    repository_path: str = Field(min_length=1)


class CreateProjectResponse(BaseModel):
    project_id: str
    repository_path: str
    status: str


class ApplyRequest(BaseModel):
    approved: bool


class Requirement(BaseModel):
    id: str
    description: str
    category: str = "behavior"
    conditions: list[str] = []
    expected_behavior: str
    boundaries: list[str] = []


class Finding(BaseModel):
    category: str
    severity: Literal["info", "warning", "error"]
    message: str
    requirement_ids: list[str] = []
    test_names: list[str] = []


class TestCase(BaseModel):
    name: str
    file: str
    target: str | None = None
    inputs: list[Any] = []
    assertions: list[str] = []
    expected_values: list[Any] = []
    smells: list[str] = []


class TestProposal(BaseModel):
    file: str
    description: str
    code: str
    finding_categories: list[str] = []


class ExecutionResult(BaseModel):
    passed: int
    failed: int
    errors: int
    duration: float
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class Evidence(BaseModel):
    execution: ExecutionResult | None = None
    requirements_total: int = 0
    requirements_covered: int = 0
    boundary_cases_total: int = 0
    boundary_cases_covered: int = 0
    meaningful_assertions: int = 0
    tests_found: int = 0
    findings: list[Finding] = []
    checks_skipped: list[str] = []


class Analysis(BaseModel):
    status: str
    srs_found: bool
    srs_path: str | None = None
    requirements: list[Requirement] = []
    tests: list[TestCase] = []
    findings: list[Finding] = []
    proposals: list[TestProposal] = []
    evidence: Evidence
    decision: Decision
    decision_reasons: list[str] = []


class AgentStep(BaseModel):
    step: int
    action: str
    observation: str
    reasoning: str
    next_action: str


class AgentStateResponse(BaseModel):
    status: str
    iteration: int
    max_iterations: int
    awaiting_approval: bool
    steps: list[AgentStep] = []


class Report(BaseModel):
    project: dict[str, Any]
    analysis: Analysis | None = None
    changes: list[str] = []
    execution: ExecutionResult | None = None
    decision: Decision
    decision_reasons: list[str] = []


# Prevent pytest from interpreting these Pydantic models as test classes.
TestCase.__test__ = False
TestProposal.__test__ = False