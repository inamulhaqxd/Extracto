import json
from typing import TypeVar, overload

from pydantic import BaseModel, ValidationError

from ai_rfp_excel.app.ai.base import (
    LLMInterface,
    LLMTimeoutError,
    ModelNotAvailableError,
    OllamaUnreachableError,
    StructuredOutputValidationError,
)
from ai_rfp_excel.app.ai.models import (
    AVAILABLE_MODELS,
    ChatMessage,
    ModelInfo,
    Role,
)
from ai_rfp_excel.app.ai.prompts.retry_error import build_retry_error_prompt
from ai_rfp_excel.app.ai.provider import extract_json_content

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(LLMInterface):
    """Mock LLM Provider for offline, deterministic testing without network or Ollama."""

    def __init__(
        self,
        default_model: str = "qwen3:4b",
        available_models: list[str] | None = None,
        responses: list[object] | None = None,
        simulate_unreachable: bool = False,
        simulate_timeout: bool = False,
    ) -> None:
        self.default_model = default_model
        self.available_models = (
            [m.lower() for m in available_models]
            if available_models is not None
            else [m.tag.lower() for m in AVAILABLE_MODELS]
        )
        self.responses: list[object] = responses or []
        self.simulate_unreachable = simulate_unreachable
        self.simulate_timeout = simulate_timeout
        self.call_history: list[dict[str, object]] = []

    def set_responses(self, responses: list[object]) -> None:
        self.responses = list(responses)

    def add_response(self, response: object) -> None:
        self.responses.append(response)

    async def is_model_available(self, model_tag: str) -> bool:
        if self.simulate_unreachable:
            raise OllamaUnreachableError("http://localhost:11434")
        target = model_tag.lower().strip()
        for avail in self.available_models:
            if target == avail or avail.startswith(f"{target}:") or target.startswith(f"{avail}:"):
                return True
            if target.split(":")[0] == avail.split(":")[0]:
                return True
        return False

    async def list_models(self) -> list[ModelInfo]:
        if self.simulate_unreachable:
            raise OllamaUnreachableError("http://localhost:11434")

        result: list[ModelInfo] = []
        for m in AVAILABLE_MODELS:
            is_avail = any(
                m.tag.lower() == avail or avail.startswith(f"{m.tag.lower()}:") or m.tag.lower().split(":")[0] == avail.split(":")[0]
                for avail in self.available_models
            )
            result.append(
                ModelInfo(
                    id=m.id,
                    name=m.name,
                    tag=m.tag,
                    label=m.label,
                    ram_usage=m.ram_usage,
                    context_length=m.context_length,
                    is_default=m.is_default,
                    is_available=is_avail,
                )
            )
        return result

    @overload
    async def chat(
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: object,
    ) -> T:
        ...

    @overload
    async def chat(
        self,
        messages: list[ChatMessage],
        response_model: None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: object,
    ) -> str:
        ...

    async def chat(
        self,
        messages: list[ChatMessage],
        response_model: type[T] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: object,
    ) -> T | str:
        model_name = model or self.default_model

        if self.simulate_unreachable:
            raise OllamaUnreachableError("http://localhost:11434")

        if self.simulate_timeout:
            raise LLMTimeoutError("Mock timeout exceeded")

        is_avail = await self.is_model_available(model_name)
        if not is_avail:
            raise ModelNotAvailableError(model_name)

        self.call_history.append(
            {
                "messages": messages,
                "response_model": response_model,
                "model": model_name,
                "temperature": temperature,
                "timeout": timeout,
            }
        )

        if not self.responses:
            if response_model:
                raise StructuredOutputValidationError(
                    schema_name=response_model.__name__,
                    raw_output="",
                    error_detail="No mock responses provided in MockLLMProvider",
                )
            return "Mock default text response"

        response_item = self.responses.pop(0)

        # If item is already an instance of response_model
        if response_model and isinstance(response_item, response_model):
            return response_item

        # If raw text string is provided
        raw_str = (
            response_item
            if isinstance(response_item, str)
            else (response_item.model_dump_json() if isinstance(response_item, BaseModel) else json.dumps(response_item))
        )

        if response_model is None:
            return raw_str

        # Test structured output validation
        clean_first = extract_json_content(raw_str)
        try:
            return response_model.model_validate_json(clean_first)
        except (ValidationError, json.JSONDecodeError) as first_err:
            # 1x retry
            if not self.responses:
                raise StructuredOutputValidationError(
                    schema_name=response_model.__name__,
                    raw_output=raw_str,
                    error_detail=str(first_err),
                ) from first_err

            retry_response_item = self.responses.pop(0)
            if isinstance(retry_response_item, response_model):
                return retry_response_item

            retry_raw = (
                retry_response_item
                if isinstance(retry_response_item, str)
                else (
                    retry_response_item.model_dump_json()
                    if isinstance(retry_response_item, BaseModel)
                    else json.dumps(retry_response_item)
                )
            )

            # Record retry message
            retry_prompt = build_retry_error_prompt(
                previous_raw_output=raw_str,
                validation_error=str(first_err),
                schema_json=json.dumps(response_model.model_json_schema(), indent=2),
            )
            self.call_history.append(
                {
                    "messages": [
                        *messages,
                        ChatMessage(role=Role.ASSISTANT, content=raw_str),
                        ChatMessage(role=Role.USER, content=retry_prompt),
                    ],
                    "response_model": response_model,
                    "model": model_name,
                    "is_retry": True,
                }
            )


            clean_retry = extract_json_content(retry_raw)
            try:
                return response_model.model_validate_json(clean_retry)
            except (ValidationError, json.JSONDecodeError) as second_err:
                raise StructuredOutputValidationError(
                    schema_name=response_model.__name__,
                    raw_output=retry_raw,
                    error_detail=str(second_err),
                ) from second_err
