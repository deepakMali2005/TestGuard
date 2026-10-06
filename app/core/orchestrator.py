from app.api.schemas import (
    Analysis,
    Evidence,
    ExecutionResult,
    Report,
)
from app.core.agent import TestGuardAgent
from app.core.decision import DecisionEngine
from app.core.evidence import EvidenceAggregator
from app.core.requirements import RequirementAnalyzer
from app.core.runner import TestRunner
from app.core.scanner import RepositoryScanner
from app.core.test_analysis import TestAnalyzer
from app.core.test_discovery import TestDiscovery
from app.core.test_generation import TestGenerator
from app.storage.repository import ProjectRecord


class TestGuardOrchestrator:
    def __init__(self, project: ProjectRecord) -> None:
        self.project = project

        self.scanner = RepositoryScanner()
        self.requirement_analyzer = RequirementAnalyzer()
        self.test_discovery = TestDiscovery()
        self.test_analyzer = TestAnalyzer()
        self.test_generator = TestGenerator()
        self.runner = TestRunner()
        self.evidence_aggregator = EvidenceAggregator()
        self.decision_engine = DecisionEngine()

        self.agent = TestGuardAgent(project.agent_state)

    def analyze(self) -> Analysis:
        scan = self.scanner.scan(
            self.project.repository_path
        )

        if scan.srs_file is None:
            analysis = Analysis(
                status="NO_SRS",
                srs_found=False,
                srs_path=None,
                requirements=[],
                tests=[],
                findings=[],
                proposals=[],
                evidence=Evidence(),
                decision="REVIEW",
                decision_reasons=[
                    "No Software Requirements Specification was found.",
                    "TestGuard requires an SRS to validate test adequacy.",
                ],
            )

            self.project.analysis = analysis
            self.agent.observe_analysis(analysis)

            return analysis

        srs_path = (
            self.project.repository_path
            / scan.srs_file
        )

        srs_text = srs_path.read_text(
            encoding="utf-8"
        )

        requirements = self.requirement_analyzer.analyze(
            srs_text
        )

        tests = self.test_discovery.discover(
            repository_root=self.project.repository_path,
            test_files=scan.test_files,
        )

        findings = self.test_analyzer.analyze(
            requirements=requirements,
            tests=tests,
        )

        proposals = self.test_generator.propose(
            repository_root=self.project.repository_path,
            requirements=requirements,
            tests=tests,
            findings=findings,
        )

        evidence = self.evidence_aggregator.aggregate(
            requirements=requirements,
            tests=tests,
            findings=findings,
        )

        decision, reasons = self.decision_engine.decide(
            evidence
        )

        analysis = Analysis(
            status="ANALYZED",
            srs_found=True,
            srs_path=str(scan.srs_file),
            requirements=requirements,
            tests=tests,
            findings=findings,
            proposals=proposals,
            evidence=evidence,
            decision=decision,
            decision_reasons=reasons,
        )

        self.project.analysis = analysis

        self.agent.observe_analysis(analysis)

        return analysis

    def apply_changes(self) -> list[str]:
        analysis = self.project.analysis

        if analysis is None:
            raise ValueError(
                "Analysis must be performed before applying changes."
            )

        if not self.project.agent_state.awaiting_approval:
            raise PermissionError(
                "Repository changes require explicit human approval."
            )

        applied = []

        for proposal in analysis.proposals:
            file_path = (
                self.project.repository_path
                / proposal.file
            )

            file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with file_path.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(proposal.code)

            applied.append(str(proposal.file))

        self.project.changes.extend(applied)

        self.agent.approve()

        return applied

    def reject_changes(self) -> None:
        self.agent.reject()

    def run_tests(self) -> ExecutionResult:
        if self.project.analysis is None:
            raise ValueError(
                "Analysis must be performed before running tests."
            )

        if self.project.agent_state.awaiting_approval:
            raise PermissionError(
                "Repository changes are awaiting explicit human approval."
            )

        execution = self.runner.run(
            self.project.repository_path
        )

        self.project.execution = execution

        # Re-scan the repository after any approved changes.
        scan = self.scanner.scan(
            self.project.repository_path
        )

        if scan.srs_file is None:
            raise ValueError(
                "The repository no longer contains an SRS."
            )

        srs_path = (
            self.project.repository_path
            / scan.srs_file
        )

        requirements = self.requirement_analyzer.analyze(
            srs_path.read_text(
                encoding="utf-8"
            )
        )

        tests = self.test_discovery.discover(
            repository_root=self.project.repository_path,
            test_files=scan.test_files,
        )

        findings = self.test_analyzer.analyze(
            requirements=requirements,
            tests=tests,
        )

        proposals = self.test_generator.propose(
            repository_root=self.project.repository_path,
            requirements=requirements,
            tests=tests,
            findings=findings,
        )

        evidence = self.evidence_aggregator.aggregate(
            requirements=requirements,
            tests=tests,
            findings=findings,
            execution=execution,
        )

        decision, reasons = self.decision_engine.decide(
            evidence
        )

        analysis = Analysis(
            status="ANALYZED",
            srs_found=True,
            srs_path=str(scan.srs_file),
            requirements=requirements,
            tests=tests,
            findings=findings,
            proposals=proposals,
            evidence=evidence,
            decision=decision,
            decision_reasons=reasons,
        )

        self.project.analysis = analysis

        self.agent.observe_execution(execution)

        return execution

    def report(self) -> Report:
        analysis = self.project.analysis

        if analysis is None:
            raise ValueError(
                "Analysis must be performed before generating a report."
            )

        execution = self.project.execution

        return Report(
            project={
                "project_id": self.project.project_id,
                "repository_path": str(
                    self.project.repository_path
                ),
            },
            analysis=analysis,
            changes=self.project.changes,
            execution=execution,
            decision=analysis.decision,
            decision_reasons=analysis.decision_reasons,
        )