from app.api.schemas import Evidence


class EvidenceAggregator:
    def aggregate(
        self,
        requirements,
        tests,
        findings,
        execution=None,
    ):
        requirements_total = len(requirements)

        covered_requirement_ids = {
            requirement_id
            for finding in findings
            if finding.category == "REQUIREMENT_COVERED"
            for requirement_id in finding.requirement_ids
        }

        requirements_covered = len(covered_requirement_ids)

        boundary_requirements = [
            requirement
            for requirement in requirements
            if requirement.boundaries
        ]

        boundary_cases_total = len(boundary_requirements)

        covered_boundary_ids = {
            requirement_id
            for finding in findings
            if finding.category == "REQUIREMENT_COVERED"
            for requirement_id in finding.requirement_ids
        }

        missing_boundary_ids = {
            requirement_id
            for finding in findings
            if finding.category == "MISSING_BOUNDARY"
            for requirement_id in finding.requirement_ids
        }

        boundary_cases_covered = len(
            (
                covered_boundary_ids
                & {
                    requirement.id
                    for requirement in boundary_requirements
                }
            )
            - missing_boundary_ids
        )

        meaningful_assertions = sum(
            1
            for test in tests
            if test.assertions
        )

        checks_skipped = []

        if execution is None:
            checks_skipped.append("behavioral_execution")

        # These engines are intentionally not implemented in the MVP yet.
        checks_skipped.extend(
            [
                "coverage",
                "mutation",
                "stability",
                "semantic_agreement",
            ]
        )

        return Evidence(
            execution=execution,
            requirements_total=requirements_total,
            requirements_covered=requirements_covered,
            boundary_cases_total=boundary_cases_total,
            boundary_cases_covered=boundary_cases_covered,
            meaningful_assertions=meaningful_assertions,
            tests_found=len(tests),
            findings=findings,
            checks_skipped=checks_skipped,
        )