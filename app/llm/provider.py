import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from dotenv import load_dotenv


load_dotenv()


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, context: str = "") -> str:
        raise NotImplementedError


class UnavailableLLMProvider(LLMProvider):
    def generate(self, prompt: str, context: str = "") -> str:
        raise RuntimeError(
            "No LLM provider is configured. "
            "Set GEMINI_API_KEY to enable LLM-assisted test generation."
        )


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv(
            "GEMINI_MODEL",
            "gemini-2.5-flash-lite",
        )

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

    def generate(self, prompt: str, context: str = "") -> str:
        full_prompt = prompt

        if context:
            full_prompt += "\n\nCONTEXT:\n" + context

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{self.model}:generateContent"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": full_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")

        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Gemini API request failed ({exc.code}): {error_body}"
            ) from exc

        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach Gemini API: {exc.reason}"
            ) from exc

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Gemini returned invalid JSON."
            ) from exc

        candidates = data.get("candidates", [])

        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])

        text_parts = [
            part.get("text", "")
            for part in parts
            if part.get("text")
        ]

        if not text_parts:
            raise RuntimeError("Gemini returned an empty response.")

        return "\n".join(text_parts)


def create_llm_provider() -> LLMProvider:
    load_dotenv()

    if os.getenv("GEMINI_API_KEY"):
        return GeminiProvider()

    return UnavailableLLMProvider()