from typing import Any, Optional

import httpx

from .llm_interface import LLMInterface, LLMResponse
from app.errors import ServiceUnavailableError, ValidationError
from app.logging_config import get_logger

logger = get_logger()


class OllamaClient(LLMInterface):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        timeout: int = 120,
    ) -> LLMResponse:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                        },
                    },
                    timeout=timeout,
                )

                if response.status_code != 200:
                    raise ValidationError(f"Ollama returned status {response.status_code}")

                data = response.json()

                return LLMResponse(
                    content=data.get("message", {}).get("content", ""),
                    model=model,
                    done=data.get("done", False),
                    total_duration=data.get("total_duration"),
                )

        except httpx.ConnectError:
            raise ServiceUnavailableError("Ollama")
        except httpx.TimeoutException:
            raise ValidationError(f"Ollama request timed out after {timeout}s")

    async def is_model_available(self, model: str) -> bool:
        try:
            models = await self.list_models()
            return any(m.get("name") == model for m in models)
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=10.0)

                if response.status_code != 200:
                    return []

                data = response.json()
                return data.get("models", [])

        except Exception:
            return []
