from app.api.schemas import (
    Analysis,
    Evidence,
    ExecutionResult,
    Report,
)
from app.core.agent import AgentDecision, TestGuardAgent
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
    """
    Coordinates TestGuard's bounded validation workflow.

    The orchestrator is responsible for:
    - executing bounded analysis tools
    - maintaining project analysis state
    - coordinating the agent
    - ensuring human approval before repository mutations
    - collecting execution/evidence
    - producing the final report

    The agent does not directly access the repository or execute commands.
    It only selects one bounded action at a time.
    """

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

    # ------------------------------------------------------------------
    # Bounded tools
    # ------------------------------------------------------------------

    def analyze_repository(self) -> Analysis:
        """
        Inspect the repository and establish the requirements baseline.

        This step intentionally does not generate or modify tests.
        """

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
                    (
                        "TestGuard requires an SRS to validate "
                        "test adequacy."
                    ),
                ],
            )

            self.project.analysis = analysis

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

        analysis = Analysis(
            status="REPOSITORY_ANALYZED",
            srs_found=True,
            srs_path=str(scan.srs_file),
            requirements=requirements,
            tests=[],
            findings=[],
            proposals=[],
            evidence=Evidence(),
            decision="REVIEW",
            decision_reasons=[],
        )

        self.project.analysis = analysis

        return analysis

    def analyze_tests(self) -> Analysis:
        """
        Discover and analyze the repository's tests against the
        established requirements baseline.
        """

        analysis = self._require_analysis()

        if not analysis.srs_found:
            raise ValueError(
                "A valid SRS is required before analyzing tests."
            )

        scan = self.scanner.scan(
            self.project.repository_path
        )

        tests = self.test_discovery.discover(
            repository_root=self.project.repository_path,
            test_files=scan.test_files,
        )

        findings = self.test_analyzer.analyze(
            requirements=analysis.requirements,
            tests=tests,
        )

        evidence = self.evidence_aggregator.aggregate(
            requirements=analysis.requirements,
            tests=tests,
            findings=findings,
        )

        decision, reasons = self.decision_engine.decide(
            evidence
        )

        analysis.status = "TESTS_ANALYZED"
        analysis.tests = tests
        analysis.findings = findings
        analysis.evidence = evidence
        analysis.decision = decision
        analysis.decision_reasons = reasons

        self.project.analysis = analysis

        return analysis

    def generate_test_proposals(self) -> Analysis:
        """
        Convert test-analysis findings into explicit proposals.

        This is a planning step only. No repository mutation occurs here.
        """

        analysis = self._require_analysis()

        if not analysis.srs_found:
            raise ValueError(
                "A valid SRS is required before generating proposals."
            )

        proposals = self.test_generator.propose(
            repository_root=self.project.repository_path,
            requirements=analysis.requirements,
            tests=analysis.tests,
            findings=analysis.findings,
        )

        analysis.proposals = proposals

        # IMPORTANT:
        # Persist the workflow transition so the next agent invocation
        # does not select generate_test_proposals again.
        analysis.status = "PROPOSALS_GENERATED"

        self.project.analysis = analysis

        return analysis

    def apply_changes(self) -> list[str]:
        """
        Apply previously proposed repository changes.

        Repository mutation is allowed only after explicit approval.
        """

        analysis = self._require_analysis()

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

            analysis.status = "CHANGES_APPLIED"
            self.project.analysis = analysis

            return applied

    def reject_changes(self) -> None:
        """
        Reject currently proposed repository changes.
        """

        self.agent.reject()

    def run_tests(self) -> ExecutionResult:
        """
        Execute the repository's tests and collect behavioral evidence.

        This step does not make the final trust decision. That is handled
        separately by evaluate_evidence().
        """

        analysis = self._require_analysis()

        if self.project.agent_state.awaiting_approval:
            raise PermissionError(
                "Repository changes are awaiting explicit human approval."
            )

        execution = self.runner.run(
            self.project.repository_path
        )

        self.project.execution = execution

        # Re-scan after any approved repository changes.
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

        # Final decision is deliberately deferred to evaluate_evidence().
        analysis = Analysis(
            status="EVIDENCE_COLLECTED",
            srs_found=True,
            srs_path=str(scan.srs_file),
            requirements=requirements,
            tests=tests,
            findings=findings,
            proposals=proposals,
            evidence=evidence,
            decision="REVIEW",
            decision_reasons=[
                "Execution evidence has been collected.",
                "Final evidence evaluation is pending.",
            ],
        )

        self.project.analysis = analysis

        return execution

    def evaluate_evidence(self) -> Analysis:
        """
        Evaluate all collected evidence and produce the final decision.
        """

        analysis = self._require_analysis()

        decision, reasons = self.decision_engine.decide(
            analysis.evidence
        )

        analysis.decision = decision
        analysis.decision_reasons = reasons
        analysis.status = "EVALUATED"

        self.project.analysis = analysis

        return analysis

    # ------------------------------------------------------------------
    # Agent orchestration
    # ------------------------------------------------------------------

    def decide_agent_action(self) -> AgentDecision:
        """
        Select exactly one bounded action based on the current workflow
        state.

        This method only decides. It does not execute the action or record
        an agent step.
        """

        analysis = self.project.analysis

        if analysis is None:
            return self.agent.decide_initial_action()

        if analysis.status == "NO_SRS":
            return AgentDecision(
                action="stop",
                observation=(
                    "No Software Requirements Specification was found."
                ),
                reasoning=(
                    "TestGuard cannot validate test adequacy without "
                    "an SRS."
                ),
            )

        if analysis.status == "REPOSITORY_ANALYZED":
            return AgentDecision(
                action="analyze_tests",
                observation=(
                    "Repository analysis completed and an SRS is available."
                ),
                reasoning=(
                    "The requirements baseline is available, so TestGuard "
                    "can inspect the test suite."
                ),
            )

        if analysis.status == "TESTS_ANALYZED":
            return AgentDecision(
                action="generate_test_proposals",
                observation="Test analysis completed.",
                reasoning=(
                    "Potential weaknesses must be converted into explicit, "
                    "reviewable proposals before deciding whether human "
                    "approval is required."
                ),
            )

        if analysis.status == "PROPOSALS_GENERATED":
            if analysis.proposals:
                return AgentDecision(
                    action="request_approval",
                    observation=(
                        f"{len(analysis.proposals)} test improvement "
                        "proposal(s) are ready for review."
                    ),
                    reasoning=(
                        "Repository mutations require explicit human "
                        "approval before they can be applied."
                    ),
                )

            return AgentDecision(
                action="run_tests",
                observation=(
                    "Test analysis completed without requiring "
                    "repository changes."
                ),
                reasoning=(
                    "There are no proposed repository mutations, so "
                    "controlled execution can collect behavioral evidence."
                ),
            )

        if analysis.status == "CHANGES_APPLIED":
            return AgentDecision(
                action="run_tests",
                observation=(
                    "Approved repository changes were applied."
                ),
                reasoning=(
                    "The modified test suite must now be executed to "
                    "collect behavioral evidence."
                ),
            )

        if analysis.status == "EVIDENCE_COLLECTED":
            return AgentDecision(
                action="evaluate_evidence",
                observation=(
                    "Controlled test execution completed and evidence "
                    "is available."
                ),
                reasoning=(
                    "The collected evidence can now be evaluated against "
                    "TestGuard's decision rules."
                ),
            )

        if analysis.status == "EVALUATED":
            return AgentDecision(
                action="finish",
                observation=(
                    f"Evidence evaluation completed with decision "
                    f"{analysis.decision}."
                ),
                reasoning=(
                    "The validation workflow has collected and evaluated "
                    "the available evidence."
                ),
            )

        return AgentDecision(
            action="finish",
            observation="The validation workflow is complete.",
            reasoning="No further bounded action is required.",
        )

    def execute_agent_action(self, action: str):
        """
        Execute exactly one bounded agent action.
        """

        if action == "analyze_repository":
            return self.analyze_repository()

        if action == "analyze_tests":
            return self.analyze_tests()

        if action == "generate_test_proposals":
            return self.generate_test_proposals()

        if action == "request_approval":
            analysis = self._require_analysis()

            return self.agent.observe_proposals(
                proposal_count=len(analysis.proposals)
            )

        if action == "apply_approved_changes":
            applied = self.apply_changes()

            if self.project.analysis is not None:
                self.project.analysis.status = "CHANGES_APPLIED"

            return applied

        if action == "run_tests":
            return self.run_tests()

        if action == "evaluate_evidence":
            return self.evaluate_evidence()

        if action == "finish":
            self.agent.complete()

            return AgentDecision(
                action="finish",
                observation="Validation workflow completed.",
                reasoning=(
                    "All required bounded validation steps have completed."
                ),
            )

        if action == "stop":
            self.agent.block()

            return AgentDecision(
                action="stop",
                observation="Validation workflow stopped.",
                reasoning=(
                    "The required requirements baseline is unavailable."
                ),
            )

        raise ValueError(
            f"Unsupported agent action: {action}"
        )

    def run_agent_step(self) -> dict:
        """
        Execute exactly one agent step.

        The decision is made first, exactly one bounded action is executed,
        and exactly one trace entry is recorded.
        """

        decision = self.decide_agent_action()

        result = self.execute_agent_action(
            decision.action
        )

        observation = decision.observation
        reasoning = decision.reasoning
        next_action = None

        if isinstance(result, AgentDecision):
            observation = result.observation
            reasoning = result.reasoning
            next_action = result.action
        elif isinstance(result, Analysis):
            next_decision = self._decision_after_analysis(
                result
            )

            observation = next_decision.observation
            reasoning = next_decision.reasoning
            next_action = next_decision.action
        elif decision.action == "run_tests":
            next_action = "evaluate_evidence"
        elif decision.action == "evaluate_evidence":
            next_action = "finish"
        elif decision.action == "finish":
            next_action = "finish"
        elif decision.action == "stop":
            next_action = "stop"
        elif decision.action == "generate_test_proposals":
            analysis = self._require_analysis()

            if analysis.proposals:
                next_action = "request_approval"
            else:
                next_action = "run_tests"
        elif decision.action == "analyze_repository":
            next_action = "analyze_tests"
        elif decision.action == "analyze_tests":
            next_action = "generate_test_proposals"

        self.agent.record_step(
            action=decision.action,
            observation=observation,
            reasoning=reasoning,
            next_action=next_action,
        )

        return {
            "action": decision.action,
            "observation": observation,
            "reasoning": reasoning,
            "result": result,
            "agent_state": self.agent.state,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def report(self) -> Report:
        analysis = self._require_analysis()

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_analysis(self) -> Analysis:
        analysis = self.project.analysis

        if analysis is None:
            raise ValueError(
                "Repository analysis must be performed first."
            )

        return analysis

    def _decision_after_analysis(
        self,
        analysis: Analysis,
    ) -> AgentDecision:
        """
        Determine the next bounded action after an analysis tool completes.

        This keeps run_agent_step() from duplicating workflow logic.
        """

        if analysis.status == "NO_SRS":
            return AgentDecision(
                action="stop",
                observation=(
                    "No Software Requirements Specification was found."
                ),
                reasoning=(
                    "TestGuard requires an SRS before test adequacy "
                    "can be evaluated."
                ),
            )

        if analysis.status == "REPOSITORY_ANALYZED":
            return AgentDecision(
                action="analyze_tests",
                observation=(
                    "Repository analysis completed and an SRS is available."
                ),
                reasoning=(
                    "The requirements baseline is available, so TestGuard "
                    "can inspect the test suite."
                ),
            )

        if analysis.status == "TESTS_ANALYZED":
            return AgentDecision(
                action="generate_test_proposals",
                observation="Test analysis completed.",
                reasoning=(
                    "Potential weaknesses must be converted into explicit, "
                    "reviewable proposals before deciding whether human "
                    "approval is required."
                ),
            )

        if analysis.status == "PROPOSALS_GENERATED":
            if analysis.proposals:
                return AgentDecision(
                    action="request_approval",
                    observation=(
                        f"{len(analysis.proposals)} proposal(s) require "
                        "explicit human approval."
                    ),
                    reasoning=(
                        "Repository mutations require explicit human "
                        "approval before they can be applied."
                    ),
                )

            return AgentDecision(
                action="run_tests",
                observation=(
                    "Test analysis completed without requiring "
                    "repository changes."
                ),
                reasoning=(
                    "There are no proposed repository mutations, so "
                    "controlled execution can collect behavioral evidence."
                ),
            )

        if analysis.status == "EVIDENCE_COLLECTED":
            return AgentDecision(
                action="evaluate_evidence",
                observation=(
                    "Controlled test execution completed and evidence "
                    "is available."
                ),
                reasoning=(
                    "The collected evidence can now be evaluated."
                ),
            )

        if analysis.status == "EVALUATED":
            return AgentDecision(
                action="finish",
                observation=(
                    f"Evidence evaluation completed with decision "
                    f"{analysis.decision}."
                ),
                reasoning=(
                    "The validation workflow has completed."
                ),
            )

        return AgentDecision(
            action="finish",
            observation="Validation workflow completed.",
            reasoning="No further bounded action is required.",
        )