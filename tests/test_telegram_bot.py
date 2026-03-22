from __future__ import annotations

import sys
import types
import unittest


class FakeBotCommand:
    def __init__(self, command: str, description: str) -> None:
        self.command = command
        self.description = description


class FakeBot:
    def __init__(self) -> None:
        self.commands: list[FakeBotCommand] | None = None

    async def set_my_commands(self, commands) -> None:
        self.commands = list(commands)


class FakeUpdater:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    async def start_polling(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1


class FakeApplication:
    def __init__(self) -> None:
        self.handlers: list[object] = []
        self.bot = FakeBot()
        self.updater = FakeUpdater()
        self.initialized = 0
        self.started = 0
        self.stopped = 0
        self.shutdowns = 0

    @classmethod
    def builder(cls):
        return cls()

    def token(self, _token: str):
        return self

    def build(self):
        return self

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        self.initialized += 1

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        self.stopped += 1

    async def shutdown(self) -> None:
        self.shutdowns += 1


class FakeCommandHandler:
    def __init__(self, command: str, callback) -> None:
        self.command = command
        self.callback = callback


telegram = types.ModuleType("telegram")
telegram.Update = type("Update", (), {})
telegram.BotCommand = FakeBotCommand

telegram_constants = types.ModuleType("telegram.constants")
telegram_constants.ParseMode = types.SimpleNamespace(MARKDOWN_V2="MarkdownV2")

telegram_ext = types.ModuleType("telegram.ext")
telegram_ext.Application = FakeApplication
telegram_ext.CommandHandler = FakeCommandHandler
telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)

sys.modules["telegram"] = telegram
sys.modules["telegram.constants"] = telegram_constants
sys.modules["telegram.ext"] = telegram_ext
sys.modules.pop("comms.telegram_bot", None)

from comms.telegram_bot import TelegramBotService


class TelegramBotServiceTests(unittest.IsolatedAsyncioTestCase):
    def build_service(self) -> TelegramBotService:
        return TelegramBotService(
            config={"telegram": {"token": "token", "chat_id": "chat-id"}},
            status_provider=lambda: {"cpu_percent": 0.0, "ram_percent": 0.0, "top_processes": []},
            processes_provider=lambda: [],
            mode_provider=lambda: "local",
        )

    async def test_start_registers_bot_commands(self) -> None:
        service = self.build_service()

        await service.start()

        assert service.application is not None
        commands = service.application.bot.commands
        self.assertIsNotNone(commands)
        self.assertEqual(
            [command.command for command in commands],
            [
                "help",
                "ping",
                "status",
                "processes",
                "mode",
                "model",
                "ask",
                "note",
                "memory",
            ],
        )
        self.assertEqual(service.application.updater.started, 1)


if __name__ == "__main__":
    unittest.main()
