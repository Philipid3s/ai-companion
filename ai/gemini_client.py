from __future__ import annotations

from ai.base import LLMClient

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover - optional dependency at runtime
    genai = None


class GeminiClient(LLMClient):
    @property
    def name(self) -> str:
        return "gemini"

    async def is_available(self) -> bool:
        return genai is not None and bool(self.config["ai"].get("gemini_api_key"))

    async def chat(self, prompt: str, context: list[dict[str, str]]) -> str:
        if genai is None:
            raise RuntimeError("google-generativeai package is not installed")

        api_key = self.config["ai"].get("gemini_api_key")
        if not api_key:
            raise RuntimeError("Gemini API key is not configured")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        history = "\n".join(f"{item['role']}: {item['content']}" for item in context)
        full_prompt = f"{history}\nuser: {prompt}" if history else prompt
        response = await model.generate_content_async(full_prompt)
        text = getattr(response, "text", "")
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return str(text)
