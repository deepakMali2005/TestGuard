from dataclasses import dataclass
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
}

SRS_FILENAMES = {
    "srs.md",
    "srs.txt",
    "requirements.md",
    "requirements.txt",
}

SOURCE_EXTENSIONS = {
    ".py",
}

TEST_PREFIXES = (
    "test_",
)

TEST_SUFFIXES = (
    "_test.py",
)


@dataclass
class RepositoryScan:
    root: Path
    files: list[Path]
    source_files: list[Path]
    test_files: list[Path]
    srs_file: Path | None


class RepositoryScanner:
    """Scans a repository for files relevant to TestGuard."""

    def scan(self, repository_path: Path) -> RepositoryScan:
        root = repository_path.resolve()

        if not root.exists():
            raise FileNotFoundError(
                f"Repository does not exist: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Repository path is not a directory: {root}"
            )

        files: list[Path] = []
        source_files: list[Path] = []
        test_files: list[Path] = []
        srs_candidates: list[Path] = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if self._should_ignore(path, root):
                continue

            relative = path.relative_to(root)

            if self._is_sensitive_file(path):
                continue

            files.append(relative)

            if self._is_srs_file(path):
                srs_candidates.append(relative)

            if path.suffix.lower() in SOURCE_EXTENSIONS:
                if self._is_test_file(path):
                    test_files.append(relative)
                else:
                    source_files.append(relative)

        srs_file = self._select_srs_file(srs_candidates)

        return RepositoryScan(
            root=root,
            files=sorted(files),
            source_files=sorted(source_files),
            test_files=sorted(test_files),
            srs_file=srs_file,
        )

    def _should_ignore(self, path: Path, root: Path) -> bool:
        try:
            relative = path.relative_to(root)
        except ValueError:
            return True

        return any(
            part in IGNORED_DIRECTORIES
            for part in relative.parts
        )

    def _is_sensitive_file(self, path: Path) -> bool:
        return path.name in {
            ".env",
            ".env.local",
            ".env.production",
            ".env.development",
        }

    def _is_srs_file(self, path: Path) -> bool:
        return path.name.lower() in SRS_FILENAMES

    def _is_test_file(self, path: Path) -> bool:
        name = path.name.lower()

        return (
            name.startswith(TEST_PREFIXES)
            or name.endswith(TEST_SUFFIXES)
        )

    def _select_srs_file(
        self,
        candidates: list[Path],
    ) -> Path | None:
        if not candidates:
            return None

        priority = {
            "srs.md": 0,
            "srs.txt": 1,
            "requirements.md": 2,
            "requirements.txt": 3,
        }

        return min(
            candidates,
            key=lambda path: (
                priority.get(path.name.lower(), 99),
                len(path.parts),
                str(path).lower(),
            ),
        )