from dataclasses import dataclass, field


@dataclass
class AgentStep:
    step: int
    action: str
    observation: str
    reasoning: str
    next_action: str


@dataclass
class AgentState:
    status: str = "READY"
    iteration: int = 0
    max_iterations: int = 3
    awaiting_approval: bool = False
    steps: list[AgentStep] = field(default_factory=list)


class TestGuardAgent:
    """
    Bounded controller for the TestGuard agentic workflow.

    The agent does not execute tools or modify repositories directly.
    It observes analysis/execution results and selects the next bounded
    action for the orchestrator.
    """

    def __init__(self, state: AgentState | None = None) -> None:
        self.state = state or AgentState()

    def observe_analysis(self, analysis) -> str:
        # Analysis should only advance the workflow once.
        if self.state.status == "COMPLETED":
            return "finish"

        if self.state.status == "BLOCKED":
            return "stop"

        self.state.iteration += 1

        if analysis.status == "NO_SRS":
            self.state.status = "BLOCKED"
            self.state.awaiting_approval = False

            self._record_step(
                action="observe_analysis",
                observation="No Software Requirements Specification was found.",
                reasoning=(
                    "TestGuard cannot validate test adequacy without "
                    "a requirements baseline."
                ),
                next_action="stop",
            )

            return "stop"

        if analysis.proposals:
            self.state.status = "AWAITING_APPROVAL"
            self.state.awaiting_approval = True

            self._record_step(
                action="observe_analysis",
                observation=(
                    f"{len(analysis.proposals)} targeted test improvement "
                    "proposal(s) were identified."
                ),
                reasoning=(
                    "Potential repository mutations require explicit "
                    "human approval before they can be applied."
                ),
                next_action="request_approval",
            )

            return "request_approval"

        self.state.status = "RUNNING"
        self.state.awaiting_approval = False

        self._record_step(
            action="observe_analysis",
            observation=(
                "Analysis completed without requiring repository changes."
            ),
            reasoning=(
                "The current evidence is sufficient to proceed to "
                "controlled test execution."
            ),
            next_action="run_tests",
        )

        return "run_tests"

    def observe_execution(self, execution) -> str:
        # A completed workflow must remain completed even if the API
        # receives another /run request. Re-running pytest should not
        # create another agent decision step.
        if self.state.status == "COMPLETED":
            return "finish"

        if self.state.status == "BLOCKED":
            return "stop"

        self.state.iteration += 1

        if execution.timed_out:
            self.state.status = "BLOCKED"
            self.state.awaiting_approval = False

            self._record_step(
                action="observe_execution",
                observation="Test execution timed out.",
                reasoning=(
                    "A timeout prevents reliable evidence collection, "
                    "so the workflow must stop rather than infer success."
                ),
                next_action="stop",
            )

            return "stop"

        if execution.errors > 0:
            self.state.status = "BLOCKED"
            self.state.awaiting_approval = False

            self._record_step(
                action="observe_execution",
                observation=(
                    f"pytest reported {execution.errors} execution error(s)."
                ),
                reasoning=(
                    "Infrastructure or execution errors make the current "
                    "evidence insufficient for a trusted decision."
                ),
                next_action="stop",
            )

            return "stop"

        if execution.failed > 0:
            self.state.status = "COMPLETED"
            self.state.awaiting_approval = False

            self._record_step(
                action="observe_execution",
                observation=(
                    f"pytest reported {execution.failed} failing test(s)."
                ),
                reasoning=(
                    "The tests executed successfully as a process, but "
                    "the observed behavior does not support a trusted result."
                ),
                next_action="finish",
            )

            return "finish"

        self.state.status = "COMPLETED"
        self.state.awaiting_approval = False

        self._record_step(
            action="observe_execution",
            observation=(
                f"pytest completed with {execution.passed} passing test(s)."
            ),
            reasoning=(
                "Execution completed successfully and the current "
                "evidence can be evaluated by the decision layer."
            ),
            next_action="finish",
        )

        return "finish"

    def approve(self) -> None:
        if not self.state.awaiting_approval:
            return

        self.state.awaiting_approval = False
        self.state.status = "RUNNING"

        self._record_step(
            action="human_approval",
            observation="Human approval was received.",
            reasoning=(
                "The proposed repository mutation is now authorized "
                "for the orchestrator to apply."
            ),
            next_action="apply_changes",
        )

    def reject(self) -> None:
        self.state.awaiting_approval = False
        self.state.status = "COMPLETED"

        self._record_step(
            action="human_rejection",
            observation="Human approval was not granted.",
            reasoning=(
                "TestGuard must not modify the repository without "
                "explicit approval."
            ),
            next_action="finish",
        )

    def _record_step(
        self,
        action,
        observation,
        reasoning,
        next_action,
    ) -> None:
        self.state.steps.append(
            AgentStep(
                step=len(self.state.steps) + 1,
                action=action,
                observation=observation,
                reasoning=reasoning,
                next_action=next_action,
            )
        )