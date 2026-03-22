from __future__ import annotations

import sys
import types
import unittest

apscheduler = types.ModuleType("apscheduler")
schedulers = types.ModuleType("apscheduler.schedulers")
asyncio_mod = types.ModuleType("apscheduler.schedulers.asyncio")
telegram = types.ModuleType("telegram")
telegram_ext = types.ModuleType("telegram.ext")
telegram_constants = types.ModuleType("telegram.constants")
aiosqlite = types.ModuleType("aiosqlite")


class FakeAsyncIOScheduler:
    def start(self) -> None:
        return None

    def add_job(self, *args, **kwargs) -> None:
        return None

    def shutdown(self, wait: bool = False) -> None:
        return None


class FakeApplication:
    @classmethod
    def builder(cls):
        return cls()

    def token(self, _token: str):
        return self

    def build(self):
        return self


asyncio_mod.AsyncIOScheduler = FakeAsyncIOScheduler
telegram.Update = type("Update", (), {})
telegram_constants.ParseMode = types.SimpleNamespace(MARKDOWN_V2="MarkdownV2")
telegram_ext.Application = FakeApplication
telegram_ext.CommandHandler = type("CommandHandler", (), {"__init__": lambda self, *args, **kwargs: None})
telegram_ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
aiosqlite.Row = dict
aiosqlite.Connection = object

async def connect(_path):
    return None

aiosqlite.connect = connect

sys.modules.setdefault("apscheduler", apscheduler)
sys.modules.setdefault("apscheduler.schedulers", schedulers)
sys.modules.setdefault("apscheduler.schedulers.asyncio", asyncio_mod)
sys.modules.setdefault("telegram", telegram)
sys.modules.setdefault("telegram.ext", telegram_ext)
sys.modules.setdefault("telegram.constants", telegram_constants)
sys.modules.setdefault("aiosqlite", aiosqlite)

from core.scheduler import CompanionScheduler


def build_config() -> dict:
    return {
        "telegram": {"token": "", "chat_id": ""},
        "presence": {
            "idle_threshold_seconds": 300,
            "mode_switch_hysteresis": 2,
        },
        "keepalive": {
            "min_interval_seconds": 180,
            "max_interval_seconds": 420,
            "mouse_delta_max_px": 3,
        },
        "monitoring": {
            "cpu_alert_threshold": 85,
            "ram_alert_threshold": 90,
            "check_interval_seconds": 30,
        },
        "ai": {
            "default_model": "ollama",
            "fallback_order": ["ollama", "groq", "gemini"],
        },
    }


class FakePresenceDetector:
    def __init__(self) -> None:
        self.mode = "local"
        self.last_marked_idle: int | None = None
        self.next_evaluation: tuple[str, bool] = ("local", False)

    def get_mode(self) -> str:
        return self.mode

    def evaluate_mode(self) -> tuple[str, bool]:
        return self.next_evaluation

    def get_idle_milliseconds(self) -> int:
        return 240000

    def mark_synthetic_input(self, observed_idle_ms: int | None = None) -> None:
        self.last_marked_idle = observed_idle_ms


class FakeMemory:
    def __init__(self, selected_model=None) -> None:
        self.selected_model = selected_model
        self.events: list[tuple[str, str, str]] = []
        self.config_writes: list[tuple[str, str]] = []

    async def initialize(self) -> None:
        return None

    async def get_config_value(self, key: str, default=None):
        if key == "selected_model":
            return self.selected_model
        return default

    async def set_config_value(self, key: str, value: str) -> None:
        self.config_writes.append((key, value))

    async def log_event(self, event_type: str, content: str, severity: str = "info") -> None:
        self.events.append((event_type, content, severity))

    async def record_alert(self, message: str, channel: str) -> None:
        self.events.append(("alert_sent", f"{channel}:{message}", "info"))

    async def close(self) -> None:
        return None


class FakeKeepalive:
    def __init__(self) -> None:
        self.enabled = 0

    def enable_execution_state(self) -> None:
        self.enabled += 1

    def next_interval_seconds(self) -> int:
        return 200

    def send_mouse_jitter(self) -> tuple[int, int]:
        return (1, -1)


class FakeTelegram:
    def __init__(self) -> None:
        self.started = 0
        self.sent: list[str] = []

    async def start(self) -> None:
        self.started += 1

    async def stop(self) -> None:
        return None

    async def send_alert(self, message: str) -> None:
        self.sent.append(message)

    async def flush_queue(self) -> None:
        return None


class FakeAIService:
    def __init__(self, response: str = "ok", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.prompts: list[str] = []

    async def chat(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.response


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_preserves_existing_selected_model(self) -> None:
        scheduler = CompanionScheduler(build_config(), FakePresenceDetector())
        scheduler.memory = FakeMemory(selected_model="groq")
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()

        await scheduler._startup()

        self.assertEqual(scheduler.memory.config_writes, [])
        self.assertEqual(scheduler.keepalive.enabled, 1)
        self.assertEqual(scheduler.telegram.started, 1)

    async def test_startup_sets_default_model_when_missing(self) -> None:
        scheduler = CompanionScheduler(build_config(), FakePresenceDetector())
        scheduler.memory = FakeMemory(selected_model=None)
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()

        await scheduler._startup()

        self.assertEqual(
            scheduler.memory.config_writes,
            [("selected_model", "ollama")],
        )

    async def test_keepalive_marks_synthetic_input_for_presence_detector(self) -> None:
        presence = FakePresenceDetector()
        scheduler = CompanionScheduler(build_config(), presence)
        scheduler.memory = FakeMemory(selected_model="ollama")
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()

        async def fake_schedule_keepalive_once() -> None:
            return None

        scheduler._schedule_keepalive_once = fake_schedule_keepalive_once

        await scheduler._run_keepalive()

        self.assertEqual(presence.last_marked_idle, 240000)
        self.assertIn(
            ("keepalive", "Sent keepalive mouse jitter dx=1 dy=-1", "info"),
            scheduler.memory.events,
        )

    async def test_chat_with_ai_updates_ui_state_during_request(self) -> None:
        presence = FakePresenceDetector()
        scheduler = CompanionScheduler(build_config(), presence)
        scheduler.memory = FakeMemory(selected_model="ollama")
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()
        scheduler.ai_service = FakeAIService(response="hello")
        states: list[str] = []
        scheduler.set_ui_state_notifier(states.append)

        response = await scheduler.chat_with_ai("hi")

        self.assertEqual(response, "hello")
        self.assertEqual(states, ["thinking", "idle"])
        self.assertIn(("ai_prompt", "hi", "info"), scheduler.memory.events)

    async def test_chat_with_ai_restores_remote_state_on_error(self) -> None:
        presence = FakePresenceDetector()
        presence.mode = "remote"
        scheduler = CompanionScheduler(build_config(), presence)
        scheduler.memory = FakeMemory(selected_model="ollama")
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()
        scheduler.ai_service = FakeAIService(error=RuntimeError("boom"))
        states: list[str] = []
        scheduler.set_ui_state_notifier(states.append)

        with self.assertRaisesRegex(RuntimeError, "boom"):
            await scheduler.chat_with_ai("hi")

        self.assertEqual(states, ["thinking", "remote"])

    async def test_presence_tick_sends_alerts_for_both_mode_transitions(self) -> None:
        presence = FakePresenceDetector()
        scheduler = CompanionScheduler(build_config(), presence)
        scheduler.memory = FakeMemory(selected_model="ollama")
        scheduler.keepalive = FakeKeepalive()
        scheduler.telegram = FakeTelegram()

        scheduler.monitor.check_alerts = lambda: []

        presence.mode = "remote"
        presence.next_evaluation = ("remote", True)
        await scheduler._presence_and_monitoring_tick()

        presence.mode = "local"
        presence.next_evaluation = ("local", True)
        await scheduler._presence_and_monitoring_tick()

        self.assertEqual(
            scheduler.telegram.sent,
            [
                "Presence mode changed to remote.",
                "Presence mode changed to local.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
