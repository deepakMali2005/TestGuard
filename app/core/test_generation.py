import json
from pathlib import Path

from app.api.schemas import TestProposal
from app.llm.provider import create_llm_provider


class TestGenerator:
    """
    Generates candidate tests from detected requirement gaps.

    TestGuard does not allow the LLM to directly modify the repository.
    The LLM only produces proposals. Human approval and the existing
    apply/pytest/evidence workflow remain responsible for the next steps.
    """

    def __init__(self):
        self.llm = create_llm_provider()

    def propose(
        self,
        repository_root: Path,
        requirements,
        tests,
        findings,
    ) -> list[TestProposal]:
        if not requirements or not tests:
            return []

        uncovered_requirements = [
            requirement
            for requirement in requirements
            if not self._requirement_is_already_covered(
                requirement,
                findings,
            )
        ]

        if not uncovered_requirements:
            return []

        target_test = tests[0]

        if not target_test.target:
            return []

        context = self._build_context(
            repository_root=repository_root,
            requirements=uncovered_requirements,
            tests=tests,
            findings=findings,
        )

        prompt = self._build_prompt(
            test_file=target_test.file,
            target=target_test.target,
        )

        try:
            response = self.llm.generate(
                prompt=prompt,
                context=context,
            )
        except RuntimeError as exc:
            print(f"[TestGuard] LLM test generation unavailable: {exc}")
            return []

        return self._parse_response(
            response=response,
            test_file=target_test.file,
        )

    def _requirement_is_already_covered(
        self,
        requirement,
        findings,
    ) -> bool:
        return any(
            finding.category == "REQUIREMENT_COVERED"
            and requirement.id in finding.requirement_ids
            for finding in findings
        )

    def _build_prompt(
        self,
        test_file: str,
        target: str,
    ) -> str:
        return f"""
You are generating candidate pytest tests for TestGuard.

Your task is to create tests for requirements that the current test
suite does not adequately cover.

Rules:

1. Use ONLY the supplied SRS, source code, existing tests and findings.
2. Do not invent APIs, functions, classes or behavior.
3. Prefer boundary cases, negative cases and missing requirements.
4. Expected values must come from the requirement, not from copying
   the current implementation blindly.
5. Generate valid pytest code.
6. Keep the tests focused and small.
7. Do not modify production code.
8. Do not use shell commands, subprocesses, network calls or file access.
9. The proposal must target the existing test file:
   {test_file}
10. The existing target function is:
   {target}

Return ONLY valid JSON in this exact structure:

{{
  "proposals": [
    {{
      "description": "Short explanation of the missing test",
      "code": "Complete pytest test function as a string",
      "finding_categories": [
        "MISSING_REQUIREMENT"
      ]
    }}
  ]
}}

If no useful test can be generated, return:

{{"proposals": []}}
""".strip()

    def _build_context(
        self,
        repository_root: Path,
        requirements,
        tests,
        findings,
    ) -> str:
        sections = []

        sections.append(
            "UNMET REQUIREMENTS:\n"
            + "\n".join(
                f"{requirement.id}: {requirement.description}"
                for requirement in requirements
            )
        )

        sections.append(
            "RELEVANT FINDINGS:\n"
            + "\n".join(
                (
                    f"- {finding.category}: "
                    f"{finding.message}"
                )
                for finding in findings
                if finding.category != "REQUIREMENT_COVERED"
            )
        )

        test_files = {
            test.file
            for test in tests
            if test.file
        }

        existing_tests = []

        for test_file in test_files:
            path = repository_root / test_file

            if not path.is_file():
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            existing_tests.append(
                f"FILE: {test_file}\n{content}"
            )

        sections.append(
            "EXISTING TEST CODE:\n"
            + "\n\n".join(existing_tests)
        )

        source_code = []

        for path in repository_root.rglob("*.py"):
            if any(
                part in {
                    ".git",
                    ".venv",
                    "venv",
                    "__pycache__",
                }
                for part in path.parts
            ):
                continue

            if path.name.startswith("test_"):
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            relative_path = path.relative_to(
                repository_root
            )

            source_code.append(
                f"FILE: {relative_path}\n{content}"
            )

        sections.append(
            "SOURCE CODE:\n"
            + "\n\n".join(source_code)
        )

        return "\n\n".join(sections)

    def _parse_response(
        self,
        response: str,
        test_file: str,
    ) -> list[TestProposal]:
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            return []

        proposals = data.get("proposals", [])

        if not isinstance(proposals, list):
            return []

        result = []

        for item in proposals:
            if not isinstance(item, dict):
                continue

            description = item.get("description")
            code = item.get("code")
            categories = item.get(
                "finding_categories",
                [],
            )

            if not isinstance(description, str):
                continue

            if not isinstance(code, str):
                continue

            if not code.strip():
                continue

            if not isinstance(categories, list):
                categories = []

            # The model never chooses the target file.
            # TestGuard forces the proposal onto the existing test file.
            result.append(
                TestProposal(
                    file=test_file,
                    description=description.strip(),
                    code=code.strip() + "\n",
                    finding_categories=[
                        category
                        for category in categories
                        if isinstance(category, str)
                    ],
                )
            )

        return result