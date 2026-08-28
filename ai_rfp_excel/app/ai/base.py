from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

from ai_rfp_excel.app.ai.models import ChatMessage, ModelInfo

T = TypeVar("T", bound=BaseModel)


# --- Custom Exception Hierarchy ---


class LLMError(Exception):
    """Base exception for all LLM errors."""


class OllamaUnreachableError(LLMError):
    """Raised when the Ollama service cannot be reached."""

    def __init__(self, base_url: str, message: str | None = None) -> None:
        self.base_url = base_url
        msg = message or f"Ollama is unreachable at {base_url}. Please ensure Ollama is installed and running."
        super().__init__(msg)


class ModelNotAvailableError(LLMError):
    """Raised when the requested model is not downloaded or available in Ollama."""

    def __init__(self, model_tag: str, message: str | None = None) -> None:
        self.model_tag = model_tag
        msg = message or f"Model '{model_tag}' is not downloaded. Please run 'ollama pull {model_tag}' manually."
        super().__init__(msg)


class StructuredOutputValidationError(LLMError):
    """Raised when the model output fails schema validation even after retry."""

    def __init__(self, schema_name: str, raw_output: str, error_detail: str) -> None:
        self.schema_name = schema_name
        self.raw_output = raw_output
        self.error_detail = error_detail
        msg = (
            f"Failed to validate structured output against schema '{schema_name}' after retry.\n"
            f"Validation error: {error_detail}\n"
            f"Raw output: {raw_output}"
        )
        super().__init__(msg)


class LLMTimeoutError(LLMError):
    """Raised when an LLM call exceeds the allowed timeout."""


# --- Abstract Base Interface ---


class LLMInterface(ABC):
    """Abstract interface defining required LLM capabilities for the RFP pipeline."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        response_model: type[T] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Send chat messages to the LLM and optionally validate response against response_model.

        If response_model is provided:
          - The LLM is instructed to output JSON matching the schema.
          - Output is parsed with Pydantic.
          - If parsing or schema validation fails, one retry is executed with error feedback.
          - If retry fails, StructuredOutputValidationError is raised.
        """

    @abstractmethod
    async def is_model_available(self, model_tag: str) -> bool:
        """Check if the given model tag is downloaded and available locally."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """List all supported models and annotate their availability status."""
