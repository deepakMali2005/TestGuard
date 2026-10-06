from dataclasses import dataclass, field
from typing import Literal


AgentAction = Literal[
    "analyze_repository",
    "analyze_tests",
    "generate_test_proposals",
    "request_approval",
    "apply_approved_changes",
    "run_tests",
    "evaluate_evidence",
    "finish",
    "stop",
]


@dataclass
class AgentStep:
    step: int
    action: str
    observation: str
    reasoning: str
    next_action: str


@dataclass
class AgentDecision:
    action: AgentAction
    observation: str
    reasoning: str


@dataclass
class AgentState:
    status: str = "READY"
    iteration: int = 0
    max_iterations: int = 8
    awaiting_approval: bool = False
    steps: list[AgentStep] = field(default_factory=list)


class TestGuardAgent:
    """
    Bounded decision controller for the TestGuard workflow.

    The agent never executes repository operations itself.

    It:
        1. selects one bounded action
        2. observes the result
        3. selects the next action

    The orchestrator records exactly one trace step for each
    executed action.
    """

    def __init__(self, state: AgentState | None = None) -> None:
        self.state = state or AgentState()

    def decide_initial_action(self) -> AgentDecision:
        if self.state.status == "COMPLETED":
            return self._terminal_decision("finish")

        if self.state.status == "BLOCKED":
            return self._terminal_decision("stop")

        self.state.status = "RUNNING"

        return AgentDecision(
            action="analyze_repository",
            observation="Agent workflow is ready to inspect the repository.",
            reasoning=(
                "TestGuard must establish repository and SRS context "
                "before reasoning about tests."
            ),
        )

    def observe_repository_analysis(
        self,
        analysis,
    ) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        if analysis.status == "NO_SRS":
            self.state.status = "BLOCKED"
            self.state.awaiting_approval = False

            return AgentDecision(
                action="stop",
                observation=(
                    "No Software Requirements Specification was found."
                ),
                reasoning=(
                    "TestGuard requires an SRS as the requirements "
                    "baseline for evidence-based validation."
                ),
            )

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

    def observe_test_analysis(
        self,
        analysis,
    ) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        return AgentDecision(
            action="generate_test_proposals",
            observation="Test analysis completed.",
            reasoning=(
                "Potential weaknesses must be converted into explicit, "
                "reviewable proposals before deciding whether human "
                "approval is required."
            ),
        )

    def observe_proposals(
        self,
        proposal_count: int,
    ) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        if proposal_count <= 0:
            self.state.status = "RUNNING"
            self.state.awaiting_approval = False

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

        self.state.status = "AWAITING_APPROVAL"
        self.state.awaiting_approval = True

        return AgentDecision(
            action="request_approval",
            observation=(
                f"{proposal_count} test improvement proposal(s) "
                "are ready for human review."
            ),
            reasoning=(
                "TestGuard must never mutate the repository without "
                "explicit human approval."
            ),
        )

    def observe_approval(
        self,
        approved: bool,
    ) -> AgentDecision:
        if not self.state.awaiting_approval:
            return AgentDecision(
                action="stop",
                observation=(
                    "No approval request is currently pending."
                ),
                reasoning=(
                    "An approval response is valid only when the agent "
                    "is waiting for approval."
                ),
            )

        self.state.awaiting_approval = False

        if not approved:
            self.state.status = "COMPLETED"

            return AgentDecision(
                action="finish",
                observation="Human approval was not granted.",
                reasoning=(
                    "Repository changes cannot be applied without "
                    "explicit human authorization."
                ),
            )

        self.state.status = "RUNNING"

        return AgentDecision(
            action="apply_approved_changes",
            observation="Human approval was granted.",
            reasoning=(
                "The proposed repository mutation is now authorized "
                "for the orchestrator to apply."
            ),
        )

    def observe_changes_applied(self) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        return AgentDecision(
            action="run_tests",
            observation="Approved test changes were applied.",
            reasoning=(
                "The modified test suite must be executed to collect "
                "behavioral evidence."
            ),
        )

    def observe_execution(
        self,
        execution,
    ) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        if execution.timed_out:
            self.state.status = "BLOCKED"

            return AgentDecision(
                action="stop",
                observation="Test execution timed out.",
                reasoning=(
                    "A timeout prevents reliable evidence collection."
                ),
            )

        if execution.errors > 0:
            self.state.status = "BLOCKED"

            return AgentDecision(
                action="stop",
                observation=(
                    f"pytest reported {execution.errors} "
                    "execution error(s)."
                ),
                reasoning=(
                    "Execution errors make the current evidence "
                    "insufficient for a reliable decision."
                ),
            )

        return AgentDecision(
            action="evaluate_evidence",
            observation=(
                f"pytest completed with {execution.passed} "
                f"passing test(s) and {execution.failed} "
                "failing test(s)."
            ),
            reasoning=(
                "Execution evidence is available and should now "
                "be evaluated before producing the final decision."
            ),
        )

    def observe_evidence(
        self,
        decision,
    ) -> AgentDecision:
        if self._is_terminal():
            return self._terminal_decision(
                "finish"
                if self.state.status == "COMPLETED"
                else "stop"
            )

        self.state.status = "COMPLETED"
        self.state.awaiting_approval = False

        return AgentDecision(
            action="finish",
            observation=(
                "Evidence evaluation produced the decision: "
                f"{decision.decision}."
            ),
            reasoning=(
                "The evidence and decision layers have produced "
                "the final bounded TestGuard result."
            ),
        )

    def complete(self) -> None:
        self.state.status = "COMPLETED"
        self.state.awaiting_approval = False

    def block(self) -> None:
        self.state.status = "BLOCKED"
        self.state.awaiting_approval = False

    def record_step(
        self,
        action: AgentAction,
        observation: str,
        reasoning: str,
        next_action: AgentAction,
    ) -> None:
        self.state.iteration += 1

        self.state.steps.append(
            AgentStep(
                step=len(self.state.steps) + 1,
                action=action,
                observation=observation,
                reasoning=reasoning,
                next_action=next_action,
            )
        )

        if self.state.iteration >= self.state.max_iterations:
            if next_action not in {"finish", "stop"}:
                self.state.status = "BLOCKED"
                self.state.awaiting_approval = False

    def approve(self) -> None:
        self.state.awaiting_approval = False
        self.state.status = "RUNNING"

    def reject(self) -> None:
        self.state.awaiting_approval = False
        self.state.status = "COMPLETED"

    def _terminal_decision(
        self,
        action: AgentAction,
    ) -> AgentDecision:
        return AgentDecision(
            action=action,
            observation=(
                "The agent workflow is already in a terminal state."
            ),
            reasoning=(
                "Terminal workflows are idempotent and must not "
                "execute additional validation actions."
            ),
        )

    def _is_terminal(self) -> bool:
        return self.state.status in {
            "COMPLETED",
            "BLOCKED",
        }

    # Backward-compatible alias.
    def observe_execution_decision(
        self,
        execution,
    ) -> AgentDecision:
        return self.observe_execution(execution)