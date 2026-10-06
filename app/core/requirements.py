import re

from app.api.schemas import Requirement


class RequirementAnalyzer:
    """
    Converts an SRS document into structured requirements.

    The MVP uses lightweight deterministic parsing. It is intentionally
    conservative: when the text cannot be confidently interpreted,
    the requirement is preserved rather than invented.
    """

    def analyze(self, text: str) -> list[Requirement]:
        text = text.strip()

        if not text:
            return []

        requirements = self._parse_numbered_requirements(text)

        if requirements:
            return requirements

        return self._parse_paragraph_requirements(text)

    def _parse_numbered_requirements(
        self,
        text: str,
    ) -> list[Requirement]:
        pattern = re.compile(
            r"(?m)^\s*(R\d+)[\s:.)-]+(.+?)(?=\n\s*R\d+[\s:.)-]+|\Z)",
            re.IGNORECASE | re.DOTALL,
        )

        matches = pattern.findall(text)

        requirements: list[Requirement] = []

        for requirement_id, description in matches:
            cleaned = self._clean_description(description)

            if not cleaned:
                continue

            requirements.append(
                self._build_requirement(
                    requirement_id.upper(),
                    cleaned,
                )
            )

        return requirements

    def _parse_paragraph_requirements(
        self,
        text: str,
    ) -> list[Requirement]:
        sentences = re.split(
            r"(?<=[.!?])\s+",
            text,
        )

        requirements: list[Requirement] = []

        for index, sentence in enumerate(sentences, start=1):
            cleaned = sentence.strip()

            if not cleaned:
                continue

            requirements.append(
                self._build_requirement(
                    f"R{index}",
                    cleaned,
                )
            )

        return requirements

    def _build_requirement(
        self,
        requirement_id: str,
        description: str,
    ) -> Requirement:
        conditions = self._extract_conditions(description)
        boundaries = self._extract_boundaries(description)
        expected_behavior = self._extract_expected_behavior(
            description
        )

        return Requirement(
            id=requirement_id,
            description=description,
            category="behavior",
            conditions=conditions,
            expected_behavior=expected_behavior,
            boundaries=boundaries,
        )

    def _extract_conditions(
        self,
        description: str,
    ) -> list[str]:
        conditions: list[str] = []

        patterns = [
            r"\bif\b[^,.]*",
            r"\bonly when\b[^,.]*",
            r"\bwhen\b[^,.]*",
            r"\bfor\b[^,.]*",
        ]

        for pattern in patterns:
            matches = re.findall(
                pattern,
                description,
                flags=re.IGNORECASE,
            )

            for match in matches:
                cleaned = match.strip(" .,:;")

                if cleaned and cleaned not in conditions:
                    conditions.append(cleaned)

        return conditions

    def _extract_boundaries(
        self,
        description: str,
    ) -> list[str]:
        boundaries: list[str] = []

        boundary_patterns = [
            r"\bgreater than\b",
            r"\bless than\b",
            r"\bequal(?: to)?\b",
            r"\bat least\b",
            r"\bat most\b",
            r"\bor less\b",
            r"\bor more\b",
            r"\bonly when\b",
        ]

        for pattern in boundary_patterns:
            if re.search(
                pattern,
                description,
                flags=re.IGNORECASE,
            ):
                boundaries.append(
                    re.search(
                        pattern,
                        description,
                        flags=re.IGNORECASE,
                    ).group(0)
                )

        numbers = re.findall(
            r"₹?\s*\d+(?:\.\d+)?",
            description,
        )

        for number in numbers:
            normalized = number.strip()

            if normalized not in boundaries:
                boundaries.append(normalized)

        return boundaries

    def _extract_expected_behavior(
        self,
        description: str,
    ) -> str:
        lowered = description.lower()

        if "no discount" in lowered:
            return "no discount"

        if "discount" in lowered:
            return "discount applied"

        if "reject" in lowered or "rejected" in lowered:
            return "request rejected"

        if "error" in lowered or "exception" in lowered:
            return "error expected"

        if "return" in lowered:
            return description

        return description

    def _clean_description(
        self,
        description: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            description,
        ).strip()