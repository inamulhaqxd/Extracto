import json
import re
from typing import Any, TypeVar

import httpx
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
from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.logging import get_logger

logger = get_logger("ai.provider")
T = TypeVar("T", bound=BaseModel)


def extract_json_content(text: str) -> str:
    """Extract clean JSON string from text or markdown code fences."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        return match.group(1).strip()
    return cleaned


class LocalLLMProvider(LLMInterface):
    """Local LLM Provider wrapping Ollama with structured validation and retry logic."""

    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.DEFAULT_LLM_MODEL
        self.temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        self.timeout = timeout if timeout is not None else float(settings.LLM_TIMEOUT_SECONDS)

    async def _get_installed_model_tags(self) -> list[str]:
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                models = data.get("models", [])
                tags = []
                for m in models:
                    tag = m.get("name") or m.get("model")
                    if tag:
                        tags.append(tag.lower())
                return tags
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as e:
            raise OllamaUnreachableError(self.base_url) from e
        except Exception as e:
            raise OllamaUnreachableError(
                self.base_url,
                message=f"Failed to query Ollama tags at {url}: {e!s}",
            ) from e

    async def is_model_available(self, model_tag: str) -> bool:
        """Check if model tag is downloaded locally in Ollama."""
        installed = await self._get_installed_model_tags()
        target = model_tag.lower().strip()
        for installed_tag in installed:
            if target == installed_tag or installed_tag.startswith(f"{target}:") or target.startswith(f"{installed_tag}:"):
                return True
            # Match base name without tag
            if target.split(":")[0] == installed_tag.split(":")[0]:
                return True
        return False

    async def list_models(self) -> list[ModelInfo]:
        """List 5 supported models annotated with their local availability."""
        installed = await self._get_installed_model_tags()
        models_list: list[ModelInfo] = []

        for m in AVAILABLE_MODELS:
            is_avail = False
            m_tag = m.tag.lower()
            for inst in installed:
                if m_tag == inst or inst.startswith(f"{m_tag}:") or m_tag.split(":")[0] == inst.split(":")[0]:
                    is_avail = True
                    break

            models_list.append(
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

        return models_list

    async def _call_ollama_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        timeout: float,
        is_json_format: bool = False,
    ) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": m.role.value, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_parallel": settings.OLLAMA_NUM_PARALLEL,
            },
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
        }

        if is_json_format:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 404:
                    raise ModelNotAvailableError(model)
                res.raise_for_status()
                data = res.json()
                msg = data.get("message", {})
                content = msg.get("content", "")
                return str(content)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError) as e:
            raise OllamaUnreachableError(self.base_url) from e
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Ollama request timed out after {timeout} seconds") from e

    async def chat(
        self,
        messages: list[ChatMessage],
        response_model: type[T] | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        model_name = model or self.default_model
        temp = temperature if temperature is not None else self.temperature
        req_timeout = timeout if timeout is not None else self.timeout

        # Check model availability first
        is_avail = await self.is_model_available(model_name)
        if not is_avail:
            raise ModelNotAvailableError(model_name)

        if response_model is None:
            return await self._call_ollama_chat(
                messages=messages,
                model=model_name,
                temperature=temp,
                timeout=req_timeout,
                is_json_format=False,
            )

        # Structured Output Mode
        first_raw = await self._call_ollama_chat(
            messages=messages,
            model=model_name,
            temperature=temp,
            timeout=req_timeout,
            is_json_format=True,
        )

        clean_first = extract_json_content(first_raw)
        try:
            return response_model.model_validate_json(clean_first)
        except (ValidationError, json.JSONDecodeError) as first_err:
            logger.warning(
                "Structured output validation failed on initial attempt. Triggering 1x retry.",
                schema=response_model.__name__,
                error=str(first_err),
            )

            # Exactly ONE retry with error feedback
            retry_prompt = build_retry_error_prompt(
                previous_raw_output=first_raw,
                validation_error=str(first_err),
                schema_json=json.dumps(response_model.model_json_schema(), indent=2),
            )

            retry_messages = [
                *messages,
                ChatMessage(role=Role.ASSISTANT, content=first_raw),
                ChatMessage(role=Role.USER, content=retry_prompt),
            ]


            second_raw = await self._call_ollama_chat(
                messages=retry_messages,
                model=model_name,
                temperature=temp,
                timeout=req_timeout,
                is_json_format=True,
            )

            clean_second = extract_json_content(second_raw)
            try:
                return response_model.model_validate_json(clean_second)
            except (ValidationError, json.JSONDecodeError) as second_err:
                logger.error(
                    "Structured output validation failed on retry attempt.",
                    schema=response_model.__name__,
                    error=str(second_err),
                )
                raise StructuredOutputValidationError(
                    schema_name=response_model.__name__,
                    raw_output=second_raw,
                    error_detail=str(second_err),
                ) from second_err
