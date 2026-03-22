from __future__ import annotations

import logging
from typing import Any

from ai.base import LLMClient
from ai.gemini_client import GeminiClient
from ai.groq_client import GroqClient
from ai.ollama_client import OllamaClient
from memory.context import load_notes
from memory.db import MemoryStore


class AIService:
    def __init__(self, config: dict[str, Any], memory_store: MemoryStore) -> None:
        self.config = config
        self.memory_store = memory_store
        self.logger = logging.getLogger("ai.service")
        self.clients: dict[str, LLMClient] = {
            "ollama": OllamaClient(config),
            "groq": GroqClient(config),
            "gemini": GeminiClient(config),
        }

    async def get_selected_model(self) -> str:
        await self.memory_store.initialize()
        selected = await self.memory_store.get_config_value(
            "selected_model", self.config["ai"]["default_model"]
        )
        return str(selected)

    async def get_backend_status(self) -> dict[str, str]:
        status: dict[str, str] = {}
        for name, client in self.clients.items():
            try:
                status[name] = "available" if await client.is_available() else "unavailable"
            except Exception as exc:
                status[name] = f"error: {exc}"
        return status

    async def chat(self, prompt: str) -> str:
        context = await self._build_context()
        client_order = await self._resolve_client_order()
        errors: list[str] = []

        for client_name in client_order:
            client = self.clients.get(client_name)
            if client is None:
                errors.append(f"Unknown client '{client_name}'")
                continue
            try:
                if not await client.is_available():
                    errors.append(f"{client_name} unavailable")
                    continue
                response = await client.chat(prompt, context)
                await self.memory_store.log_event(
                    "ai_chat",
                    f"AI response generated via {client_name}",
                )
                return response
            except Exception as exc:
                self.logger.warning("AI client %s failed: %s", client_name, exc)
                errors.append(f"{client_name} failed: {exc}")

        raise RuntimeError("No AI backend succeeded. " + "; ".join(errors))

    async def _resolve_client_order(self) -> list[str]:
        selected = await self.get_selected_model()
        fallback_order = list(self.config["ai"].get("fallback_order", []))
        ordered = [selected]
        for name in fallback_order:
            if name not in ordered:
                ordered.append(name)
        return ordered

    async def _build_context(self) -> list[dict[str, str]]:
        notes = await load_notes()
        if not notes:
            return []

        note_blocks = "\n\n".join(
            f"# {note['name']}\n{note['content'].strip()}" for note in notes
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are the AI Windows Companion. Use the following long-term memory "
                    f"notes when relevant:\n\n{note_blocks}"
                ),
            }
        ]
