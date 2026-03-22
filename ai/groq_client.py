from __future__ import annotations

from ai.base import LLMClient

try:
    from groq import AsyncGroq
except ImportError:  # pragma: no cover - optional dependency at runtime
    AsyncGroq = None


class GroqClient(LLMClient):
    @property
    def name(self) -> str:
        return "groq"

    async def is_available(self) -> bool:
        return AsyncGroq is not None and bool(self.config["ai"].get("groq_api_key"))

    async def chat(self, prompt: str, context: list[dict[str, str]]) -> str:
        if AsyncGroq is None:
            raise RuntimeError("groq package is not installed")

        api_key = self.config["ai"].get("groq_api_key")
        if not api_key:
            raise RuntimeError("Groq API key is not configured")

        client = AsyncGroq(api_key=api_key)
        messages = context + [{"role": "user", "content": prompt}]
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Groq returned an empty response")
        return str(content)
