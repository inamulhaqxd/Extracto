from typing import Any, Optional

from .llm_interface import LLMInterface, LLMResponse


class MockLLMProvider(LLMInterface):
    def __init__(self):
        self.responses: dict[str, str] = {}
        self.default_response: str = '{"status": "COMPLIANT", "confidence": 0.9}'
        self.call_count: int = 0
        self.calls: list[dict] = []

    def set_response(self, model: str, response: str):
        self.responses[model] = response

    def set_default_response(self, response: str):
        self.default_response = response

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        timeout: int = 120,
    ) -> LLMResponse:
        self.call_count += 1
        self.calls.append({
            "model": model,
            "messages": messages,
            "temperature": temperature,
        })

        content = self.responses.get(model, self.default_response)

        return LLMResponse(
            content=content,
            model=model,
            done=True,
            total_duration=0.1,
        )

    async def is_model_available(self, model: str) -> bool:
        return True

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {"name": "qwen3:4b", "size": 2500000000},
            {"name": "qwen2.5:3b", "size": 1800000000},
            {"name": "phi3.5:3.8b", "size": 2200000000},
            {"name": "gemma3:4b", "size": 2400000000},
            {"name": "llama3.2:3b", "size": 1700000000},
        ]

    def reset(self):
        self.call_count = 0
        self.calls = []
        self.responses = {}
