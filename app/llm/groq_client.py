"""Groq LLM client wrapper.

This is the only module in the codebase that imports the Groq SDK directly.
Isolating it here means every other layer (agent nodes, services) depends
on a single `generate(prompt) -> str` call and never touches provider-specific
types, so swapping providers later only touches this file.
"""

from groq import APIError, Groq

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError
from app.core.logger import get_logger

logger = get_logger(__name__)


class GroqClient:
    """Thin wrapper around the Groq chat completions API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.groq_model
        self._client = Groq(api_key=settings.groq_api_key)

    def generate(self, prompt: str) -> str:
        """Send a single-turn prompt to Groq and return the completion text.

        Raises:
            ExternalServiceError: if the Groq API call fails for any reason.
        """
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = completion.choices[0].message.content
            return content.strip() if content else ""
        except APIError as exc:
            logger.error("Groq API call failed: %s", exc)
            raise ExternalServiceError(f"Groq API call failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - any unexpected SDK/network failure
            logger.error("Unexpected error calling Groq API: %s", exc)
            raise ExternalServiceError(f"Unexpected error calling Groq API: {exc}") from exc