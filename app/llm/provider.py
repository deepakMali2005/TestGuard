from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Interface for optional LLM capabilities.

    The core TestGuard workflow must remain functional without
    an LLM provider.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: str = "",
    ) -> str:
        """Generate a response from the supplied prompt/context."""
        raise NotImplementedError


class UnavailableLLMProvider(LLMProvider):
    """
    Default provider used when no external LLM is configured.

    Deterministic TestGuard functionality must not depend on an
    external model being available.
    """

    def generate(
        self,
        prompt: str,
        context: str = "",
    ) -> str:
        raise RuntimeError(
            "No LLM provider is configured. "
            "TestGuard's deterministic analysis can run "
            "without an LLM."
        )