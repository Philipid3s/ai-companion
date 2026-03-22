from __future__ import annotations

import shutil
import sys
import types
import unittest
from pathlib import Path


class _FakeCursor:
    async def fetchone(self):
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.row_factory = None

    async def executescript(self, _script: str) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def execute(self, _query: str, _params=()):
        return _FakeCursor()


aiosqlite = types.ModuleType("aiosqlite")
aiosqlite.Row = dict
aioqlite_connection = _FakeConnection
aiosqlite.Connection = _FakeConnection

async def connect(_path):
    return _FakeConnection()

aiosqlite.connect = connect
sys.modules["aiosqlite"] = aiosqlite

from ai.service import AIService


class FakeMemoryStore:
    def __init__(self, selected_model: str = "groq") -> None:
        self.selected_model = selected_model
        self.logged: list[tuple[str, str, str]] = []

    async def initialize(self) -> None:
        return None

    async def get_config_value(self, key: str, default=None):
        if key == "selected_model":
            return self.selected_model
        return default

    async def log_event(self, event_type: str, content: str, severity: str = "info") -> None:
        self.logged.append((event_type, content, severity))


class FakeClient:
    def __init__(self, name: str, available: bool, response: str | None = None, error: str | None = None) -> None:
        self._name = name
        self.available = available
        self.response = response
        self.error = error
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return self.available

    async def chat(self, prompt: str, context: list[dict[str, str]]) -> str:
        self.calls.append((prompt, context))
        if self.error:
            raise RuntimeError(self.error)
        assert self.response is not None
        return self.response


class AIServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.notes_dir = Path("tests/.tmp_ai_notes")
        if self.notes_dir.exists():
            shutil.rmtree(self.notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        (self.notes_dir / "profile.md").write_text("favorite color: teal", encoding="utf-8")

    def tearDown(self) -> None:
        if self.notes_dir.exists():
            shutil.rmtree(self.notes_dir)

    async def test_chat_uses_selected_model_first_then_fallback(self) -> None:
        config = {
            "ai": {
                "default_model": "ollama",
                "fallback_order": ["ollama", "groq", "gemini"],
            }
        }
        memory_store = FakeMemoryStore(selected_model="groq")
        service = AIService(config, memory_store)
        service.clients = {
            "groq": FakeClient("groq", available=True, error="boom"),
            "ollama": FakeClient("ollama", available=True, response="local response"),
            "gemini": FakeClient("gemini", available=False),
        }

        original_build_context = service._build_context

        async def fake_build_context() -> list[dict[str, str]]:
            return [{"role": "system", "content": "memory note"}]

        service._build_context = fake_build_context  # type: ignore[method-assign]
        response = await service.chat("hello")

        self.assertEqual(response, "local response")
        self.assertEqual(service.clients["groq"].calls[0][0], "hello")
        self.assertEqual(service.clients["ollama"].calls[0][1][0]["content"], "memory note")
        self.assertTrue(any(event[0] == "ai_chat" for event in memory_store.logged))
        service._build_context = original_build_context  # type: ignore[method-assign]

    async def test_build_context_includes_markdown_notes(self) -> None:
        config = {
            "ai": {
                "default_model": "ollama",
                "fallback_order": ["ollama", "groq", "gemini"],
            }
        }
        memory_store = FakeMemoryStore()
        service = AIService(config, memory_store)

        from ai import service as service_module
        original_load_notes = service_module.load_notes

        async def fake_load_notes():
            return [{"name": "profile.md", "content": "favorite color: teal"}]

        service_module.load_notes = fake_load_notes
        context = await service._build_context()
        service_module.load_notes = original_load_notes

        self.assertEqual(context[0]["role"], "system")
        self.assertIn("profile.md", context[0]["content"])
        self.assertIn("favorite color: teal", context[0]["content"])


if __name__ == "__main__":
    unittest.main()
