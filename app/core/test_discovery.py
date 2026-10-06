import ast
from pathlib import Path

from app.api.schemas import TestCase


class TestDiscovery:
    """Discovers and structurally analyzes pytest tests."""

    def discover(
        self,
        repository_root: Path,
        test_files: list[Path],
    ) -> list[TestCase]:
        tests: list[TestCase] = []

        for relative_path in test_files:
            absolute_path = repository_root / relative_path

            try:
                source = absolute_path.read_text(
                    encoding="utf-8"
                )
                tree = ast.parse(source)
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue

            tests.extend(
                self._extract_tests(
                    tree=tree,
                    relative_path=relative_path,
                )
            )

        return tests

    def _extract_tests(
        self,
        tree: ast.AST,
        relative_path: Path,
    ) -> list[TestCase]:
        tests: list[TestCase] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if not node.name.startswith("test_"):
                continue

            tests.append(
                self._analyze_test_function(
                    node,
                    relative_path,
                )
            )

        return tests

    def _analyze_test_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        relative_path: Path,
    ) -> TestCase:
        calls: list[str] = []
        assertions: list[str] = []
        expected_values: list[object] = []
        inputs: list[object] = []
        smells: list[str] = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                target = self._call_target(child)

                if target:
                    calls.append(target)

                inputs.extend(
                    self._extract_call_arguments(child)
                )

            elif isinstance(child, ast.Assert):
                assertion = self._format_assertion(child)

                if assertion:
                    assertions.append(assertion)

                expected = self._extract_expected_value(
                    child.test
                )

                if expected is not None:
                    expected_values.append(expected)

        target = calls[0] if calls else None

        if not assertions:
            smells.append("NO_ASSERTION")
        elif len(assertions) == 1:
            smells.append("WEAK_ASSERTION")

        if not calls:
            smells.append("NO_TARGET_CALL")

        return TestCase(
            name=node.name,
            file=str(relative_path),
            target=target,
            inputs=inputs,
            assertions=assertions,
            expected_values=expected_values,
            smells=smells,
        )

    def _call_target(
        self,
        node: ast.Call,
    ) -> str | None:
        if isinstance(node.func, ast.Name):
            return node.func.id

        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            current: ast.AST | None = node.func

            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value

            if isinstance(current, ast.Name):
                parts.append(current.id)

            return ".".join(reversed(parts))

        return None

    def _extract_call_arguments(
        self,
        node: ast.Call,
    ) -> list[object]:
        values: list[object] = []

        for argument in node.args:
            value = self._literal_value(argument)

            if value is not None:
                values.append(value)

        return values

    def _format_assertion(
        self,
        node: ast.Assert,
    ) -> str | None:
        try:
            return ast.unparse(node.test)
        except Exception:
            return None

    def _extract_expected_value(
        self,
        expression: ast.AST,
    ) -> object | None:
        if not isinstance(expression, ast.Compare):
            return None

        if len(expression.comparators) != 1:
            return None

        return self._literal_value(
            expression.comparators[0]
        )

    def _literal_value(
        self,
        node: ast.AST,
    ) -> object | None:
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            return None