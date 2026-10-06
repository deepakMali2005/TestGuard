from app.api.schemas import Decision, Evidence


class DecisionEngine:
    """
    Produces the final three-way TestGuard decision.

    The MVP uses transparent deterministic rules. Every decision
    includes human-readable reasons.
    """

    def decide(
        self,
        evidence: Evidence,
    ) -> tuple[Decision, list[str]]:
        reasons: list[str] = []

        execution = evidence.execution

        # ---------------------------------------------------------
        # REJECT
        # ---------------------------------------------------------

        if evidence.tests_found == 0:
            reasons.append(
                "No executable tests were found."
            )
            return "REJECT", reasons

        if execution is not None:
            if execution.timed_out:
                reasons.append(
                    "Test execution timed out."
                )
                return "REJECT", reasons

            if execution.errors > 0:
                reasons.append(
                    "Test execution produced runtime errors."
                )
                return "REJECT", reasons

        severe_findings = [
            finding
            for finding in evidence.findings
            if finding.severity == "error"
        ]

        if any(
            finding.category in {
                "WEAK_ASSERTION",
                "IMPLEMENTATION_ANCHORED",
            }
            for finding in severe_findings
        ):
            reasons.append(
                "At least one test provides insufficient "
                "or structurally invalid evidence."
            )
            return "REJECT", reasons

        # ---------------------------------------------------------
        # REVIEW
        # ---------------------------------------------------------

        if execution is not None and execution.failed > 0:
            reasons.append(
                "One or more tests failed during execution."
            )
            return "REVIEW", reasons

        missing_requirement_findings = [
            finding
            for finding in evidence.findings
            if finding.category == "MISSING_REQUIREMENT"
        ]

        if missing_requirement_findings:
            reasons.append(
                "One or more requirements do not have "
                "clear supporting tests."
            )

        missing_boundary_findings = [
            finding
            for finding in evidence.findings
            if finding.category == "MISSING_BOUNDARY"
        ]

        if missing_boundary_findings:
            reasons.append(
                "Important boundary cases are not adequately covered."
            )

        negative_findings = [
            finding
            for finding in evidence.findings
            if finding.category == "MISSING_NEGATIVE_CASE"
        ]

        if negative_findings:
            reasons.append(
                "Important negative cases are not adequately covered."
            )

        if (
            evidence.requirements_total > 0
            and evidence.requirements_covered
            < evidence.requirements_total
        ):
            reasons.append(
                "Requirement coverage is incomplete."
            )

        if (
            evidence.boundary_cases_total > 0
            and evidence.boundary_cases_covered
            < evidence.boundary_cases_total
        ):
            reasons.append(
                "Boundary evidence is incomplete."
            )

        if reasons:
            return "REVIEW", reasons

        # ---------------------------------------------------------
        # TRUSTED
        # ---------------------------------------------------------

        if execution is None:
            reasons.append(
                "Execution evidence has not been collected."
            )
            return "REVIEW", reasons

        if execution.passed == 0:
            reasons.append(
                "No tests passed successfully."
            )
            return "REVIEW", reasons

        reasons.extend(
            [
                "Required tests executed successfully.",
                "No major structural evidence problems were detected.",
                "Available requirement and boundary evidence "
                "is sufficiently complete.",
            ]
        )

        reasons.append(
            "TRUSTED means sufficient evidence under the current "
            "TestGuard checks; it does not prove correctness."
        )

        return "TRUSTED", reasons