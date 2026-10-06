import re

from app.api.schemas import Finding


class TestAnalyzer:
    def analyze(self, requirements, tests):
        findings = []

        if not tests:
            findings.append(
                Finding(
                    category="MISSING_TEST",
                    severity="error",
                    message="No tests were discovered for the supplied repository.",
                )
            )
            for requirement in requirements:
                findings.append(
                    Finding(
                        category="MISSING_REQUIREMENT",
                        severity="error",
                        message=(
                            f"No test provides evidence for requirement "
                            f"{requirement.id}: {requirement.description}"
                        ),
                        requirement_ids=[requirement.id],
                    )
                )
            return findings

        for test in tests:
            findings.extend(self._analyze_test(test))

        findings.extend(
            self._analyze_requirement_coverage(requirements, tests)
        )
        findings.extend(
            self._analyze_boundary_coverage(requirements, tests)
        )
        findings.extend(
            self._analyze_negative_cases(requirements, tests)
        )
        findings.extend(self._detect_redundancy(tests))

        return findings

    def _analyze_test(self, test):
        findings = []

        if "NO_ASSERTION" in test.smells:
            findings.append(
                Finding(
                    category="WEAK_ASSERTION",
                    severity="error",
                    message=(
                        f"Test '{test.name}' does not contain an assertion."
                    ),
                    test_names=[test.name],
                )
            )
        elif "WEAK_ASSERTION" in test.smells:
            findings.append(
                Finding(
                    category="WEAK_ASSERTION",
                    severity="warning",
                    message=(
                        f"Test '{test.name}' contains only one assertion "
                        "and provides limited evidence."
                    ),
                    test_names=[test.name],
                )
            )

        if "NO_TARGET_CALL" in test.smells:
            findings.append(
                Finding(
                    category="IMPLEMENTATION_ANCHORED",
                    severity="warning",
                    message=(
                        f"Test '{test.name}' does not appear to call "
                        "a target function."
                    ),
                    test_names=[test.name],
                )
            )

        return findings

    def _analyze_requirement_coverage(self, requirements, tests):
        findings = []

        for requirement in requirements:
            matching_tests = [
                test
                for test in tests
                if self._matches_requirement(requirement, test)
            ]

            if matching_tests:
                findings.append(
                    Finding(
                        category="REQUIREMENT_COVERED",
                        severity="info",
                        message=(
                            f"Requirement {requirement.id} is supported by "
                            f"test(s): {', '.join(t.name for t in matching_tests)}."
                        ),
                        requirement_ids=[requirement.id],
                        test_names=[t.name for t in matching_tests],
                    )
                )
            else:
                findings.append(
                    Finding(
                        category="MISSING_REQUIREMENT",
                        severity="error",
                        message=(
                            f"No discovered test provides clear evidence for "
                            f"requirement {requirement.id}: "
                            f"{requirement.description}"
                        ),
                        requirement_ids=[requirement.id],
                    )
                )

        return findings

    def _analyze_boundary_coverage(self, requirements, tests):
        findings = []

        for requirement in requirements:
            if not requirement.boundaries:
                continue

            if not any(
                self._matches_requirement(requirement, test)
                for test in tests
            ):
                findings.append(
                    Finding(
                        category="MISSING_BOUNDARY",
                        severity="warning",
                        message=(
                            f"Boundary condition for requirement "
                            f"{requirement.id} is not covered by a "
                            "targeted test."
                        ),
                        requirement_ids=[requirement.id],
                    )
                )

        return findings

    def _analyze_negative_cases(self, requirements, tests):
        findings = []

        for requirement in requirements:
            description = requirement.description.lower()

            if "no discount" not in description:
                continue

            if "non-premium" in description:
                covered = any(
                    self._is_non_premium_test(test)
                    for test in tests
                )
            elif "equal to" in description:
                covered = any(
                    self._is_exact_threshold_test(requirement, test)
                    for test in tests
                )
            elif "less than" in description:
                covered = any(
                    self._is_below_threshold_test(requirement, test)
                    for test in tests
                )
            else:
                covered = True

            if not covered:
                findings.append(
                    Finding(
                        category="MISSING_NEGATIVE_CASE",
                        severity="warning",
                        message=(
                            f"Important negative case for requirement "
                            f"{requirement.id} is not covered."
                        ),
                        requirement_ids=[requirement.id],
                    )
                )

        return findings

    def _matches_requirement(self, requirement, test):
        description = requirement.description.lower()

        if self._is_non_premium_requirement(description):
            return self._matches_non_premium_requirement(
                requirement, test
            )

        threshold = self._extract_threshold(description)
        amount = self._extract_amount(test)

        if "premium" in description:
            if not self._contains_premium_customer(test):
                return False

        if threshold is not None and amount is not None:
            if "greater than" in description:
                if amount <= threshold:
                    return False

            if "less than" in description:
                if amount >= threshold:
                    return False

            if "equal to" in description:
                if amount != threshold:
                    return False

        if "20%" in description and amount is not None:
            expected = self._extract_expected_value(test)

            if expected is None:
                return False

            expected_discount = amount * 0.8

            if abs(float(expected) - expected_discount) > 0.01:
                return False

        if "no discount" in description and amount is not None:
            expected = self._extract_expected_value(test)

            if expected is None:
                return False

            if abs(float(expected) - float(amount)) > 0.01:
                return False

        return self._has_relevant_assertion(test)

    def _matches_non_premium_requirement(self, requirement, test):
        if not self._is_non_premium_test(test):
            return False

        amount = self._extract_amount(test)
        expected = self._extract_expected_value(test)

        if amount is None or expected is None:
            return False

        return abs(float(expected) - float(amount)) <= 0.01

    def _contains_premium_customer(self, test):
        values = [str(value).lower() for value in test.inputs]

        return any(
            value == "premium"
            for value in values
        )

    def _is_non_premium_test(self, test):
        values = [str(value).lower() for value in test.inputs]

        return any(
            value in {"regular", "non-premium", "nonpremium"}
            for value in values
        )

    def _is_non_premium_requirement(self, description):
        return "non-premium" in description

    def _is_exact_threshold_test(self, requirement, test):
        threshold = self._extract_threshold(requirement.description)
        amount = self._extract_amount(test)

        return (
            threshold is not None
            and amount is not None
            and amount == threshold
        )

    def _is_below_threshold_test(self, requirement, test):
        threshold = self._extract_threshold(requirement.description)
        amount = self._extract_amount(test)

        return (
            threshold is not None
            and amount is not None
            and amount < threshold
        )

    def _extract_threshold(self, description):
        matches = re.findall(
            r"₹?\s*(\d+(?:\.\d+)?)",
            description,
        )

        if not matches:
            return None

        values = [float(value) for value in matches]

        # Ignore percentage values such as 20%.
        values = [value for value in values if value != 20]

        return values[-1] if values else None

    def _extract_amount(self, test):
        numeric_values = []

        for value in test.inputs:
            if isinstance(value, bool):
                continue

            if isinstance(value, (int, float)):
                numeric_values.append(float(value))

        if numeric_values:
            return numeric_values[0]

        return None

    def _extract_expected_value(self, test):
        if not test.expected_values:
            return None

        value = test.expected_values[0]

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return value

        return None

    def _has_relevant_assertion(self, test):
        return bool(test.assertions)

    def _detect_redundancy(self, tests):
        findings = []
        signatures = {}

        for test in tests:
            signature = (
                test.target,
                tuple(test.inputs),
            )

            signatures.setdefault(signature, []).append(test.name)

        for names in signatures.values():
            if len(names) <= 1:
                continue

            findings.append(
                Finding(
                    category="REDUNDANT_TEST",
                    severity="warning",
                    message=(
                        "Multiple tests appear to exercise the same target "
                        "with the same inputs: "
                        + ", ".join(names)
                    ),
                    test_names=names,
                )
            )

        return findings