from __future__ import annotations

from typing import Any

from ai.base import LLMClient

try:
    from ollama import AsyncClient
except ImportError:  # pragma: no cover - optional dependency at runtime
    AsyncClient = None


class OllamaClient(LLMClient):
    @property
    def name(self) -> str:
        return "ollama"

    async def is_available(self) -> bool:
        ai_config = self.config["ai"]
        return AsyncClient is not None and bool(ai_config.get("ollama_url"))

    async def chat(self, prompt: str, context: list[dict[str, str]]) -> str:
        if AsyncClient is None:
            raise RuntimeError("ollama package is not installed")

        ai_config = self.config["ai"]
        client = AsyncClient(host=ai_config["ollama_url"])
        messages = context + [{"role": "user", "content": prompt}]
        response = await client.chat(model=ai_config["ollama_model"], messages=messages)
        content = response.get("message", {}).get("content")
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return str(content)
