from types import SimpleNamespace

from app.core.agent import TestGuardAgent as Agent


def test_agent_selects_repository_analysis_without_recording_it():
    agent = Agent()

    decision = agent.decide_initial_action()

    assert decision.action == "analyze_repository"
    assert agent.state.status == "RUNNING"
    assert agent.state.iteration == 0
    assert len(agent.state.steps) == 0


def test_agent_blocks_when_srs_is_missing():
    agent = Agent()

    agent.decide_initial_action()

    analysis = SimpleNamespace(
        status="NO_SRS",
        proposals=[],
    )

    decision = agent.observe_repository_analysis(
        analysis
    )

    assert decision.action == "stop"
    assert agent.state.status == "BLOCKED"
    assert agent.state.awaiting_approval is False


def test_agent_requires_approval_before_changes():
    agent = Agent()

    analysis = SimpleNamespace(
        proposals=[
            SimpleNamespace(
                description="Add missing boundary test"
            )
        ],
    )

    decision = agent.observe_test_analysis(
        analysis
    )

    assert decision.action == "generate_test_proposals"

    decision = agent.observe_proposals(
        proposal_count=1
    )

    assert decision.action == "request_approval"
    assert agent.state.status == "AWAITING_APPROVAL"
    assert agent.state.awaiting_approval is True

    decision = agent.observe_approval(
        approved=True
    )

    assert decision.action == "apply_approved_changes"
    assert agent.state.status == "RUNNING"
    assert agent.state.awaiting_approval is False


def test_agent_moves_from_execution_to_evidence():
    agent = Agent()

    execution = SimpleNamespace(
        timed_out=False,
        errors=0,
        failed=0,
        passed=4,
    )

    decision = agent.observe_execution(
        execution
    )

    assert decision.action == "evaluate_evidence"

    final_decision = SimpleNamespace(
        decision="TRUSTED"
    )

    decision = agent.observe_evidence(
        final_decision
    )

    assert decision.action == "finish"
    assert agent.state.status == "COMPLETED"


def test_agent_records_one_step_per_executed_action():
    agent = Agent()

    agent.record_step(
        action="analyze_repository",
        observation="Repository inspected.",
        reasoning="SRS context is required first.",
        next_action="analyze_tests",
    )

    assert agent.state.iteration == 1
    assert len(agent.state.steps) == 1
    assert agent.state.steps[0].action == "analyze_repository"
    assert agent.state.steps[0].next_action == "analyze_tests"

def test_agent_advances_after_proposals_are_generated():
    agent = Agent()

    agent.decide_initial_action()

    analysis = SimpleNamespace(
        status="TESTS_ANALYZED",
        proposals=[],
    )

    decision = agent.observe_test_analysis(analysis)
    assert decision.action == "generate_test_proposals"

    decision = agent.observe_proposals(proposal_count=0)

    assert decision.action == "run_tests"
    assert agent.state.status == "RUNNING" 