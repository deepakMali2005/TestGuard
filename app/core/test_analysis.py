import json
import re

from app.api.schemas import Finding
from app.llm.provider import create_llm_provider


class TestAnalyzer:
    def __init__(self, llm=None):
        self.llm = llm or create_llm_provider()

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

        semantic_matches = self._semantic_matches(
            requirements,
            tests,
        )

        findings.extend(
            self._analyze_requirement_coverage(
                requirements,
                tests,
                semantic_matches,
            )
        )

        findings.extend(
            self._analyze_boundary_coverage(
                requirements,
                tests,
                semantic_matches,
            )
        )

        findings.extend(
            self._detect_redundancy(tests)
        )

        return findings

    def _analyze_test(self, test):
        findings = []

        if (
            "NO_ASSERTION" in test.smells
            and not self._uses_exception_assertion(test)
        ):
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

    def _analyze_requirement_coverage(
        self,
        requirements,
        tests,
        semantic_matches,
    ):
        findings = []

        for requirement in requirements:
            matching_tests = [
                test
                for test in tests
                if (
                    self._matches_requirement(
                        requirement,
                        test,
                    )
                    or test.name
                    in semantic_matches.get(
                        requirement.id,
                        set(),
                    )
                )
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
                        test_names=[
                            t.name
                            for t in matching_tests
                        ],
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

    def _analyze_boundary_coverage(
        self,
        requirements,
        tests,
        semantic_matches,
    ):
        findings = []

        for requirement in requirements:
            if not requirement.boundaries:
                continue

            if not any(
                (
                    self._matches_requirement(
                        requirement,
                        test,
                    )
                    or test.name
                    in semantic_matches.get(
                        requirement.id,
                        set(),
                    )
                )
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

    def _matches_requirement(
        self,
        requirement,
        test,
    ):
        """
        Deterministic baseline for requirement-to-test alignment.

        This intentionally does not try to become a semantic engine.
        Semantic equivalence that cannot be established reliably from
        structure/text is delegated to _semantic_matches().
        """

        if requirement.id.lower() in test.name.lower():
            return True

        requirement_text = " ".join(
            [
                requirement.description,
                *requirement.conditions,
                requirement.expected_behavior,
                *requirement.boundaries,
            ]
        ).lower()

        test_text = " ".join(
            [
                test.name.replace("_", " "),
                *[
                    str(value)
                    for value in test.inputs
                ],
                *[
                    str(value)
                    for value in test.expected_values
                ],
                *test.assertions,
            ]
        ).lower()

        requirement_tokens = self._meaningful_tokens(
            requirement_text
        )

        test_tokens = self._meaningful_tokens(
            test_text
        )

        if not requirement_tokens or not test_tokens:
            return False

        requirement_negative = (
            self._is_negative_requirement(
                requirement
            )
        )

        test_negative = self._is_negative_test(
            test
        )

        if requirement_negative != test_negative:
            return False

        lexical_overlap = sum(
            1
            for requirement_token in requirement_tokens
            if any(
                self._tokens_match(
                    requirement_token,
                    test_token,
                )
                for test_token in test_tokens
            )
        )

        numeric_overlap = (
            self._extract_numbers(
                requirement_text
            )
            & self._extract_numbers(
                test_text
            )
        )

        expected_behavior_tokens = (
            self._meaningful_tokens(
                requirement.expected_behavior
            )
        )

        expected_behavior_overlap = sum(
            1
            for requirement_token
            in expected_behavior_tokens
            if any(
                self._tokens_match(
                    requirement_token,
                    test_token,
                )
                for test_token in test_tokens
            )
        )

        if requirement_negative:
            return (
                lexical_overlap >= 2
                or expected_behavior_overlap >= 1
                or (
                    bool(numeric_overlap)
                    and lexical_overlap >= 1
                )
            )

        return (
            lexical_overlap >= 3
            and self._has_relevant_assertion(test)
        )

    def _semantic_matches(
        self,
        requirements,
        tests,
    ):
        """
        Use the LLM only for semantic equivalence missed by
        deterministic evidence.

        Example:
            "username that already exists"
            and
            "duplicate username"

        can describe the same requirement without sharing
        the same lexical wording.
        """

        unmatched = [
            requirement
            for requirement in requirements
            if not any(
                self._matches_requirement(
                    requirement,
                    test,
                )
                for test in tests
            )
        ]

        if not unmatched:
            return {}

        test_descriptions = []

        for test in tests:
            test_descriptions.append(
                {
                    "name": test.name,
                    "target": test.target,
                    "inputs": test.inputs,
                    "expected_values": test.expected_values,
                    "assertions": test.assertions,
                }
            )

        prompt = """
You are the semantic requirement-alignment component of TestGuard.

Determine whether an existing pytest test semantically tests one of the
unmatched SRS requirements.

Semantic equivalence is allowed even when wording differs.

For example:

Requirement:
" A username that already exists must be rejected."

Test:
"test_duplicate_username"

These can describe the same behavior because "duplicate username"
and "username that already exists" are semantically equivalent.

Rules:

1. Use ONLY the supplied requirement and test information.
2. Do not infer behavior that is absent from the requirement.
3. A test must actually exercise and assert the required behavior.
4. Do not treat merely similar domain words as sufficient evidence.
5. Return only high-confidence semantic matches.
6. If uncertain, do not match.
7. Do not invent missing requirements.
8. Do not judge implementation correctness.
9. Do not generate or modify test code.

Return ONLY JSON:

{
  "matches": [
    {
      "requirement_id": "R4",
      "test_name": "test_duplicate_username"
    }
  ]
}

If there are no high-confidence matches, return:

{
  "matches": []
}
""".strip()

        context = json.dumps(
            {
                "unmatched_requirements": [
                    {
                        "id": requirement.id,
                        "description": requirement.description,
                        "conditions": requirement.conditions,
                        "expected_behavior": (
                            requirement.expected_behavior
                        ),
                        "boundaries": requirement.boundaries,
                    }
                    for requirement in unmatched
                ],
                "tests": test_descriptions,
            },
            indent=2,
            default=str,
        )

        try:
            response = self.llm.generate(
                prompt,
                context,
            )

            data = json.loads(response)

        except (
            RuntimeError,
            json.JSONDecodeError,
            TypeError,
        ):
            return {}

        if not isinstance(data, dict):
            return {}

        matches = {}

        for item in data.get(
            "matches",
            [],
        ):
            if not isinstance(item, dict):
                continue

            requirement_id = item.get(
                "requirement_id"
            )

            test_name = item.get(
                "test_name"
            )

            valid_requirement = any(
                requirement.id == requirement_id
                for requirement in unmatched
            )

            valid_test = any(
                test.name == test_name
                for test in tests
            )

            if (
                valid_requirement
                and valid_test
            ):
                matches.setdefault(
                    requirement_id,
                    set(),
                ).add(test_name)

        return matches

    def _is_negative_requirement(
        self,
        requirement,
    ):
        text = " ".join(
            [
                requirement.description,
                requirement.expected_behavior,
                *requirement.conditions,
            ]
        ).lower()

        return any(
            marker in text
            for marker in (
                "reject",
                "rejected",
                "invalid",
                "error",
                "exception",
                "must not",
                "should not",
                "not allowed",
                "denied",
                "deny",
            )
        )

    def _is_negative_test(
        self,
        test,
    ):
        text = " ".join(
            [
                test.name.replace(
                    "_",
                    " ",
                ),
                *[
                    str(value)
                    for value in test.inputs
                ],
                *[
                    str(value)
                    for value in test.expected_values
                ],
                *test.assertions,
            ]
        ).lower()

        return (
            any(
                marker in text
                for marker in (
                    "reject",
                    "rejected",
                    "error",
                    "exception",
                    "invalid",
                    "duplicate",
                    "missing",
                    "short",
                    "denied",
                    "deny",
                    "not allowed",
                    "must not",
                    "should not",
                )
            )
            or test.target == "pytest.raises"
        )

    def _meaningful_tokens(
        self,
        text,
    ):
        stop_words = {
            "a",
            "an",
            "the",
            "must",
            "should",
            "be",
            "is",
            "are",
            "to",
            "of",
            "and",
            "or",
            "for",
            "with",
            "that",
            "this",
            "than",
            "then",
            "when",
            "user",
            "request",
        }

        tokens = re.findall(
            r"[a-zA-Z0-9]+",
            text.lower(),
        )

        return {
            token
            for token in tokens
            if (
                token not in stop_words
                and len(token) > 2
            )
        }

    def _extract_numbers(
        self,
        text,
    ):
        return set(
            re.findall(
                r"\d+(?:\.\d+)?",
                text,
            )
        )

    def _tokens_match(
        self,
        left,
        right,
    ):
        if left == right:
            return True

        if (
            len(left) < 4
            or len(right) < 4
        ):
            return False

        return (
            left.startswith(right)
            or right.startswith(left)
        )

    def _uses_exception_assertion(
        self,
        test,
    ):
        return test.target == "pytest.raises"

    def _has_relevant_assertion(
        self,
        test,
    ):
        return (
            bool(test.assertions)
            or self._uses_exception_assertion(test)
        )

    def _detect_redundancy(
        self,
        tests,
    ):
        findings = []
        signatures = {}

        for test in tests:
            signature = (
                test.target,
                tuple(test.inputs),
            )

            signatures.setdefault(
                signature,
                [],
            ).append(test.name)

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