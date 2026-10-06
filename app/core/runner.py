import re
import subprocess
import sys
import time
from pathlib import Path

from app.api.schemas import ExecutionResult


class TestRunner:
    """Runs the repository's pytest suite in a controlled subprocess."""

    DEFAULT_TIMEOUT = 30

    def run(
        self,
        repository_root: Path,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> ExecutionResult:
        start_time = time.perf_counter()

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=repository_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )

            duration = time.perf_counter() - start_time

            return self._build_result(
                completed.returncode,
                completed.stdout,
                completed.stderr,
                duration,
            )

        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start_time

            stdout = self._decode_output(
                exc.stdout
            )
            stderr = self._decode_output(
                exc.stderr
            )

            return ExecutionResult(
                passed=0,
                failed=0,
                errors=0,
                duration=duration,
                exit_code=-1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
            )

        except OSError as exc:
            duration = time.perf_counter() - start_time

            return ExecutionResult(
                passed=0,
                failed=0,
                errors=1,
                duration=duration,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=False,
            )

    def _build_result(
        self,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration: float,
    ) -> ExecutionResult:
        passed = self._extract_count(
            stdout,
            "passed",
        )

        failed = self._extract_count(
            stdout,
            "failed",
        )

        errors = self._extract_count(
            stdout,
            "error",
        )

        return ExecutionResult(
            passed=passed,
            failed=failed,
            errors=errors,
            duration=duration,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
        )

    def _extract_count(
        self,
        output: str,
        label: str,
    ) -> int:
        pattern = rf"(\d+)\s+{re.escape(label)}"

        match = re.search(
            pattern,
            output,
            flags=re.IGNORECASE,
        )

        if match is None:
            return 0

        return int(match.group(1))

    def _decode_output(
        self,
        output,
    ) -> str:
        if output is None:
            return ""

        if isinstance(output, bytes):
            return output.decode(
                errors="replace"
            )

        return str(output)