from abc import ABC, abstractmethod
from typing import Any, Optional

from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    done: bool
    total_duration: Optional[float] = None


class LLMInterface(ABC):
    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        timeout: int = 120,
    ) -> LLMResponse:
        pass

    @abstractmethod
    async def is_model_available(self, model: str) -> bool:
        pass

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        pass
