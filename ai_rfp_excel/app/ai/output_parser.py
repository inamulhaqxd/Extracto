import json
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

from app.ai.llm_interface import LLMInterface
from app.logging_config import get_logger

logger = get_logger()


class ExtractionResult(BaseModel):
    entity_type: str
    specifications: list[dict[str, Any]]


class ComplianceResult(BaseModel):
    status: str
    confidence: float
    evidence: list[dict[str, Any]]
    reasoning: str


class ClassificationResult(BaseModel):
    category: str
    confidence: float
    subcategory: Optional[str] = None


class MappingResult(BaseModel):
    matched_column: str
    confidence: float
    mapping_method: str


class StructuredOutputParser:
    def __init__(self, llm: LLMInterface):
        self.llm = llm

    async def parse_with_retry(
        self,
        model: str,
        messages: list[dict[str, str]],
        output_model: type[BaseModel],
        max_retries: int = 1,
    ) -> Optional[BaseModel]:
        for attempt in range(max_retries + 1):
            try:
                response = await self.llm.chat(model=model, messages=messages)

                data = self._extract_json(response.content)
                if data is None:
                    logger.warning("failed_to_parse_json", attempt=attempt + 1)
                    if attempt < max_retries:
                        messages = self._add_error_context(messages, "Invalid JSON format")
                    continue

                return output_model(**data)

            except ValidationError as e:
                logger.warning(
                    "validation_failed",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < max_retries:
                    messages = self._add_error_context(messages, str(e))

            except Exception as e:
                logger.error("parsing_error", error=str(e))
                break

        return None

    def _extract_json(self, text: str) -> Optional[dict]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}") + 1

        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        return None

    def _add_error_context(
        self,
        messages: list[dict[str, str]],
        error: str,
    ) -> list[dict[str, str]]:
        new_messages = messages.copy()
        new_messages.append({
            "role": "user",
            "content": f"The previous response had a validation error: {error}. Please fix and return valid JSON.",
        })
        return new_messages
