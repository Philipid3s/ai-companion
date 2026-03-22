from __future__ import annotations

import asyncio
from typing import Any

from PyQt6.QtCore import QPoint, QRectF, QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QCursor, QPainter
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from paths import ASSETS_DIR
from ui.bubble_widget import BubbleWidget
from ui.cli_panel import CLIPanel
from ui.settings_window import SettingsWindow
from ui.sprite_widget import SpriteWidget


class CompanionWindow(QWidget):
    def __init__(self, config: dict, presence_detector, **_) -> None:
        super().__init__()
        self.config = config
        self.presence_detector = presence_detector
        self.scheduler = None
        self._drag_offset: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dragged = False
        self._assets_dir = ASSETS_DIR

        self.setWindowTitle("AI Windows Companion")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(150, 150)

        self.sprite = SpriteWidget(self._assets_dir, self)
        self.sprite.move(33, 20)

        self.bubble = BubbleWidget(int(self.config["ui"]["bubble_duration_ms"]), self)
        self.cli_panel = CLIPanel(config, self)
        self.cli_panel.set_command_handler(self.handle_command)
        self.cli_panel.append_output("Companion CLI ready.")
        self.settings_window = SettingsWindow(config, self)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_ui)
        self.refresh_timer.start(1000)
        self.refresh_ui()
        self._move_to_corner()
        QTimer.singleShot(500, lambda: self.show_message("Companion online.", "idle"))

    def bind_scheduler(self, scheduler: Any) -> None:
        self.scheduler = scheduler
        if hasattr(scheduler, "set_ui_notifier"):
            scheduler.set_ui_notifier(self.show_message)
        if hasattr(scheduler, "set_ui_state_notifier"):
            scheduler.set_ui_state_notifier(self.set_sprite_state)
        self.settings_window.bind_scheduler(scheduler)
        self._schedule_coroutine(self._restore_position())

    def refresh_ui(self) -> None:
        if self.sprite.state == "thinking":
            desired_state = "thinking"
        else:
            mode = self.presence_detector.get_mode()
            desired_state = "remote" if mode == "remote" else "idle"
        if self.sprite.state != desired_state:
            self.sprite.set_state(desired_state)
        self.setToolTip(f"AI Companion\nMode: {self.presence_detector.get_mode()}")
        self.update()

    def set_sprite_state(self, state: str) -> None:
        self.sprite.set_state(state)

    def show_message(self, message: str, state: str | None = None) -> None:
        if state is not None:
            self.sprite.set_state(state)
        if self.presence_detector.get_mode() == "local":
            self.bubble.queue_message(message)
        self.cli_panel.append_output(message)

    def handle_command(self, command: str) -> str:
        if command == "status":
            if self.scheduler is None:
                return f"Mode: {self.presence_detector.get_mode()}"
            snapshot = self.scheduler.get_status_snapshot()
            self._schedule_coroutine(self._emit_runtime_status())
            return (
                f"Mode: {self.presence_detector.get_mode()} | "
                f"CPU: {snapshot['cpu_percent']:.1f}% | RAM: {snapshot['ram_percent']:.1f}%"
            )
        if command == "processes":
            if self.scheduler is None:
                return "Monitoring service is not attached."
            processes = self.scheduler.get_top_processes()
            if not processes:
                return "No process data available."
            return "\n".join(
                f"{item['name']} pid={item['pid']} cpu={item['cpu_percent']:.1f}%"
                for item in processes[:5]
            )
        if command.startswith("model "):
            model_name = command.split(" ", 1)[1].strip()
            if not model_name:
                return "Usage: model <name>"
            if model_name not in {"ollama", "groq", "gemini"}:
                return "Model must be one of: ollama, groq, gemini"
            if self.scheduler is None:
                return f"Requested model switch to {model_name}."
            self._schedule_coroutine(self._set_model(model_name))
            return f"Switching model to {model_name}..."
        if command == "memory":
            if self.scheduler is None:
                return "Memory service is not attached."
            self._schedule_coroutine(self._emit_memory_notes())
            return "Loading memory notes..."
        if command.startswith("note "):
            note = command.split(" ", 1)[1].strip()
            if not note:
                return "Usage: note <text>"
            if self.scheduler is None:
                return f"Queued note: {note}"
            self._schedule_coroutine(self._append_note(note))
            return "Saving note to memory/notes/journal.md..."
        if command.startswith("ask "):
            prompt = command.split(" ", 1)[1].strip()
            if not prompt:
                return "Usage: ask <prompt>"
            if self.scheduler is None:
                return "AI service is not attached."
            self._schedule_coroutine(self._ask_ai(prompt))
            return "Sending prompt to AI backend..."
        return "Unknown command. Try: status, processes, model <name>, memory, note <text>, ask <prompt>"

    async def _set_model(self, model_name: str) -> None:
        assert self.scheduler is not None
        selected = await self.scheduler.set_selected_model(model_name)
        self.show_message(f"Active model set to {selected}.", "idle")
        await self.settings_window.refresh_from_runtime()

    async def _append_note(self, note: str) -> None:
        assert self.scheduler is not None
        path = await self.scheduler.append_memory_note(note)
        self.show_message(f"Saved note to {path}.", "idle")

    async def _ask_ai(self, prompt: str) -> None:
        assert self.scheduler is not None
        try:
            response = await self.scheduler.chat_with_ai(prompt)
            self.show_message(response, "idle")
        except Exception as exc:
            self.show_message(f"AI request failed: {exc}", "alert")

    async def _emit_runtime_status(self) -> None:
        if self.scheduler is None:
            return
        status = await self.scheduler.get_runtime_status()
        health = ", ".join(f"{k}={v}" for k, v in status["ai_health"].items())
        self.cli_panel.append_output(f"Selected model: {status['model']}")
        self.cli_panel.append_output(f"Autostart: {status['autostart']}")
        self.cli_panel.append_output(f"Backends: {health}")

    async def _emit_memory_notes(self) -> None:
        if self.scheduler is None:
            return
        notes = await self.scheduler.list_memory_notes()
        if notes:
            self.cli_panel.append_output("Memory notes: " + ", ".join(notes))
        else:
            self.cli_panel.append_output("Memory notes: none")

    async def _restore_position(self) -> None:
        if self.scheduler is None:
            return
        saved = await self.scheduler.get_companion_position()
        if saved is not None:
            self.move(saved["x"], saved["y"])
            self.cli_panel.sync_to_parent()

    async def _persist_position(self) -> None:
        if self.scheduler is None:
            return
        await self.scheduler.save_companion_position(self.x(), self.y())

    def _schedule_coroutine(self, coroutine) -> None:
        asyncio.create_task(coroutine)

    def _move_to_corner(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        margin = int(self.config["ui"]["margin_px"])
        geometry = screen.availableGeometry()
        x = geometry.right() - self.width() - margin
        y = geometry.bottom() - self.height() - margin
        self.move(x, y)
        self.cli_panel.sync_to_parent()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        shadow_rect = QRectF(18, 100, 114, 28)
        painter.setBrush(QColor(15, 23, 42, 58))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(shadow_rect)
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.globalPosition().toPoint()
            self._drag_offset = self._press_pos - self.frameGeometry().topLeft()
            self._dragged = False
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            current = event.globalPosition().toPoint()
            if self._press_pos is not None and (current - self._press_pos).manhattanLength() > 6:
                self._dragged = True
            self.move(current - self._drag_offset)
            self.cli_panel.sync_to_parent()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self._dragged:
            self.cli_panel.toggle()
        elif event.button() == Qt.MouseButton.LeftButton and self._dragged:
            self._schedule_coroutine(self._persist_position())
        self._drag_offset = None
        self._press_pos = None
        self._dragged = False
        super().mouseReleaseEvent(event)

    def _show_context_menu(self) -> None:
        menu = QMenu(self)
        for model_name in ("ollama", "groq", "gemini"):
            action = QAction(f"Model: {model_name}", self)
            action.triggered.connect(
                lambda _checked=False, name=model_name: self.handle_command(f"model {name}")
            )
            menu.addAction(action)
        menu.addSeparator()
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        menu.exec(QCursor.pos())

    def _open_settings(self) -> None:
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()
        self._schedule_coroutine(self.settings_window.refresh_from_runtime())
