from pathlib import Path

from app.api.schemas import TestProposal


class TestGenerator:
    def propose(
        self,
        repository_root: Path,
        requirements,
        tests,
        findings,
    ) -> list[TestProposal]:
        if not tests:
            return []

        target_test = tests[0]
        target = target_test.target

        if not target:
            return []

        proposals = []

        for requirement in requirements:
            if self._requirement_is_already_covered(
                requirement,
                findings,
            ):
                continue

            proposal = self._build_proposal(
                requirement=requirement,
                target=target,
                test_file=target_test.file,
            )

            if proposal:
                proposals.append(proposal)

        return proposals

    def _requirement_is_already_covered(
        self,
        requirement,
        findings,
    ):
        return any(
            finding.category == "REQUIREMENT_COVERED"
            and requirement.id in finding.requirement_ids
            for finding in findings
        )

    def _build_proposal(
        self,
        requirement,
        target,
        test_file,
    ):
        description = requirement.description.lower()

        if "equal to" in description and "no discount" in description:
            return TestProposal(
                file=test_file,
                description=(
                    f"Add an exact-threshold test for {requirement.id}."
                ),
                code=(
                    f"\n\ndef test_{requirement.id.lower()}_exact_threshold():\n"
                    f"    assert {target}(1000, \"premium\") == 1000\n"
                ),
                finding_categories=[
                    "MISSING_REQUIREMENT",
                    "MISSING_BOUNDARY",
                    "MISSING_NEGATIVE_CASE",
                ],
            )

        if "less than" in description and "no discount" in description:
            return TestProposal(
                file=test_file,
                description=(
                    f"Add a below-threshold test for {requirement.id}."
                ),
                code=(
                    f"\n\ndef test_{requirement.id.lower()}_below_threshold():\n"
                    f"    assert {target}(999, \"premium\") == 999\n"
                ),
                finding_categories=[
                    "MISSING_REQUIREMENT",
                    "MISSING_BOUNDARY",
                    "MISSING_NEGATIVE_CASE",
                ],
            )

        if "non-premium" in description:
            return TestProposal(
                file=test_file,
                description=(
                    f"Add a non-premium customer test for {requirement.id}."
                ),
                code=(
                    f"\n\ndef test_{requirement.id.lower()}_non_premium():\n"
                    f"    assert {target}(1200, \"regular\") == 1200\n"
                ),
                finding_categories=[
                    "MISSING_REQUIREMENT",
                    "MISSING_NEGATIVE_CASE",
                ],
            )

        return None