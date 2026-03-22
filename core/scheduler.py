from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ai.service import AIService
from comms.telegram_bot import TelegramBotService
from core.keepalive import KeepAliveService
from core.monitor import SystemMonitor
from integrations import autostart
from memory.context import append_note, load_notes
from memory.db import MemoryStore


class CompanionScheduler:
    def __init__(self, config: dict, presence_detector: Any, **_: Any) -> None:
        self.config = config
        self.presence_detector = presence_detector
        self.logger = logging.getLogger("core.scheduler")
        self.scheduler = AsyncIOScheduler()
        self.monitor = SystemMonitor(config)
        self.keepalive = KeepAliveService(config)
        self.memory = MemoryStore()
        self.ai_service = AIService(config, self.memory)
        self.telegram = TelegramBotService(
            config=config,
            status_provider=self.monitor.get_status_snapshot,
            processes_provider=self.monitor.get_top_processes_by_cpu,
            mode_provider=self.presence_detector.get_mode,
            ask_provider=self.chat_with_ai,
            model_getter=self.get_selected_model,
            model_setter=self.set_selected_model,
            note_provider=self.append_memory_note,
            memory_provider=self.list_memory_notes,
            health_provider=self.get_backend_status,
            queue_loader=self._load_pending_telegram_messages,
            queue_saver=self._save_pending_telegram_message,
            queue_remover=self._remove_pending_telegram_message,
        )
        self.ui_notifier: Callable[[str, str | None], None] | None = None
        self.ui_state_notifier: Callable[[str], None] | None = None
        self._started = False

    def set_ui_notifier(self, notifier: Callable[[str, str | None], None]) -> None:
        self.ui_notifier = notifier

    def set_ui_state_notifier(self, notifier: Callable[[str], None]) -> None:
        self.ui_state_notifier = notifier

    def get_status_snapshot(self) -> dict[str, Any]:
        return self.monitor.get_status_snapshot()

    def get_top_processes(self) -> list[dict[str, Any]]:
        return self.monitor.get_top_processes_by_cpu()

    async def get_runtime_status(self) -> dict[str, Any]:
        snapshot = self.monitor.get_status_snapshot()
        return {
            **snapshot,
            "mode": self.presence_detector.get_mode(),
            "model": await self.get_selected_model(),
            "ai_health": await self.get_backend_status(),
            "autostart": self.is_autostart_enabled(),
        }

    async def set_selected_model(self, model_name: str) -> str:
        await self.memory.initialize()
        await self.memory.set_config_value("selected_model", model_name)
        await self.memory.log_event("model_change", f"Selected model changed to {model_name}")
        return model_name

    async def get_selected_model(self) -> str:
        await self.memory.initialize()
        selected = await self.memory.get_config_value(
            "selected_model", self.config["ai"]["default_model"]
        )
        return str(selected)

    async def append_memory_note(self, note: str) -> str:
        path = await append_note(note)
        await self.memory.initialize()
        await self.memory.log_event("memory_note", f"Appended note to {path.name}")
        return str(path)

    async def list_memory_notes(self) -> list[str]:
        notes = await load_notes()
        return [note["name"] for note in notes]

    async def save_companion_position(self, x: int, y: int) -> None:
        await self.memory.initialize()
        await self.memory.set_config_value("companion_position", {"x": x, "y": y})

    async def get_companion_position(self) -> dict[str, int] | None:
        await self.memory.initialize()
        value = await self.memory.get_config_value("companion_position")
        if isinstance(value, dict) and "x" in value and "y" in value:
            return {"x": int(value["x"]), "y": int(value["y"])}
        return None

    async def chat_with_ai(self, prompt: str) -> str:
        self._set_ui_state("thinking")
        try:
            await self.memory.initialize()
            await self.memory.log_event("ai_prompt", prompt)
            return await self.ai_service.chat(prompt)
        finally:
            self._set_ui_state("remote" if self.presence_detector.get_mode() == "remote" else "idle")

    async def get_backend_status(self) -> dict[str, str]:
        return await self.ai_service.get_backend_status()

    def is_autostart_enabled(self) -> bool:
        return autostart.is_enabled()

    async def set_autostart_enabled(self, enabled: bool) -> bool:
        result = autostart.set_enabled(enabled)
        await self.memory.initialize()
        await self.memory.set_config_value("autostart_enabled", result)
        await self.memory.log_event("autostart", f"Autostart set to {result}")
        return result

    async def _load_pending_telegram_messages(self) -> list[str]:
        await self.memory.initialize()
        return await self.memory.list_pending_messages("telegram")

    async def _save_pending_telegram_message(self, message: str) -> None:
        await self.memory.initialize()
        await self.memory.enqueue_message("telegram", message)

    async def _remove_pending_telegram_message(self, message: str) -> None:
        await self.memory.initialize()
        await self.memory.remove_pending_message("telegram", message)

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.start()
        self.scheduler.add_job(
            self._startup,
            id="startup",
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        interval_seconds = int(self.config["monitoring"]["check_interval_seconds"])
        self.scheduler.add_job(
            self._presence_and_monitoring_tick,
            "interval",
            seconds=interval_seconds,
            id="presence-monitoring",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._schedule_keepalive_once,
            id="keepalive-bootstrap",
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        self._started = True

    async def shutdown(self) -> None:
        if not self._started:
            return
        await self.telegram.stop()
        await self.memory.close()
        self.scheduler.shutdown(wait=False)
        self._started = False

    async def _startup(self) -> None:
        await self.memory.initialize()
        selected_model = await self.memory.get_config_value("selected_model")
        if selected_model is None:
            await self.memory.set_config_value(
                "selected_model", self.config["ai"]["default_model"]
            )

        try:
            self.keepalive.enable_execution_state()
        except Exception as exc:
            self.logger.warning("Failed to enable execution state: %s", exc)
            await self.memory.log_event(
                "startup_error",
                f"Failed to enable execution state: {exc}",
                severity="warning",
            )

        try:
            await self.telegram.start()
        except Exception as exc:
            self.logger.warning("Failed to start Telegram bot: %s", exc)
            await self.memory.log_event(
                "startup_error",
                f"Failed to start Telegram bot: {exc}",
                severity="warning",
            )

        await self.memory.log_event(
            "startup",
            "Companion scheduler initialized",
        )
        self._notify_ui("Companion services are online.", "idle")

    async def _presence_and_monitoring_tick(self) -> None:
        mode, changed = self.presence_detector.evaluate_mode()
        if changed:
            await self.memory.log_event("mode_change", f"Presence mode switched to {mode}")
            self._notify_ui(
                f"Presence mode switched to {mode}.",
                "remote" if mode == "remote" else "idle",
            )
            if mode == "remote":
                await self._notify_remote_mode()

        alerts = self.monitor.check_alerts()
        for alert in alerts:
            await self.memory.log_event("alert", alert, severity="warning")
            if mode == "local":
                self._notify_ui(alert, "alert")
            await self._send_alert(alert)

        await self.telegram.flush_queue()

    async def _schedule_keepalive_once(self) -> None:
        next_interval = self.keepalive.next_interval_seconds()
        self.scheduler.add_job(
            self._run_keepalive,
            id="keepalive-once",
            replace_existing=True,
            next_run_time=datetime.now() + timedelta(seconds=next_interval),
        )
        self.logger.info("Next keepalive scheduled in %s seconds", next_interval)

    async def _run_keepalive(self) -> None:
        synthetic_idle_ms: int | None = None
        if hasattr(self.presence_detector, "get_idle_milliseconds"):
            synthetic_idle_ms = self.presence_detector.get_idle_milliseconds()

        try:
            dx, dy = self.keepalive.send_mouse_jitter()
            if hasattr(self.presence_detector, "mark_synthetic_input"):
                self.presence_detector.mark_synthetic_input(synthetic_idle_ms)
            await self.memory.log_event(
                "keepalive",
                f"Sent keepalive mouse jitter dx={dx} dy={dy}",
            )
        except Exception as exc:
            self.logger.warning("Keepalive jitter failed: %s", exc)
            await self.memory.log_event(
                "keepalive_error",
                f"Keepalive jitter failed: {exc}",
                severity="warning",
            )
        await self._schedule_keepalive_once()

    async def _notify_remote_mode(self) -> None:
        await self._send_alert("Presence mode changed to remote.")

    async def _send_alert(self, message: str) -> None:
        try:
            await self.telegram.send_alert(message)
            await self.memory.record_alert(message, "telegram")
        except Exception as exc:
            self.logger.warning("Failed to deliver Telegram alert: %s", exc)

    def _notify_ui(self, message: str, state: str | None = None) -> None:
        if self.ui_notifier is not None:
            self.ui_notifier(message, state)

    def _set_ui_state(self, state: str) -> None:
        if self.ui_state_notifier is not None:
            self.ui_state_notifier(state)
