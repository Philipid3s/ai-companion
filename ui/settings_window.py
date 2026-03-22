from __future__ import annotations

import asyncio
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class SettingsWindow(QWidget):
    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.scheduler = None
        self._tasks: set[asyncio.Task[Any]] = set()

        self.setWindowTitle("Companion Settings")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(440, 380)
        self.setStyleSheet(
            "background: rgba(8, 12, 24, 245); color: #e5e7eb;"
            "QLabel#sectionTitle { color: #f8fafc; font-size: 15px; font-weight: 600; }"
            "QLabel#sectionHint { color: #94a3b8; }"
            "QComboBox, QTextEdit { background: rgba(15, 23, 42, 255); color: #f8fafc; border: 1px solid rgba(148, 163, 184, 70); border-radius: 8px; padding: 6px; }"
            "QPushButton { background: rgba(59, 130, 246, 210); color: white; padding: 8px 12px; border-radius: 8px; }"
            "QCheckBox { spacing: 8px; }"
        )

        self.model_combo = QComboBox()
        self.model_combo.addItems(["ollama", "groq", "gemini"])

        self.autostart_checkbox = QCheckBox("Open the companion when Windows starts")
        self.health_view = QTextEdit()
        self.health_view.setReadOnly(True)
        self.health_view.setPlaceholderText("Backend availability will appear here...")

        overview_title = QLabel("General")
        overview_title.setObjectName("sectionTitle")
        overview_hint = QLabel("Choose the active AI provider and startup behavior.")
        overview_hint.setObjectName("sectionHint")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.addRow("AI provider", self.model_combo)
        form.addRow("Startup", self.autostart_checkbox)

        status_title = QLabel("Backend Status")
        status_title.setObjectName("sectionTitle")
        status_hint = QLabel("Detected availability for each configured backend.")
        status_hint.setObjectName("sectionHint")

        self.refresh_button = QPushButton("Refresh Status")
        self.refresh_button.clicked.connect(lambda: self._schedule(self.refresh_from_runtime()))
        self.save_button = QPushButton("Save Changes")
        self.save_button.clicked.connect(lambda: self._schedule(self.save_settings()))

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(overview_title)
        layout.addWidget(overview_hint)
        layout.addLayout(form)
        layout.addSpacing(8)
        layout.addWidget(status_title)
        layout.addWidget(status_hint)
        layout.addWidget(self.health_view, 1)
        layout.addLayout(buttons)

    def bind_scheduler(self, scheduler: Any) -> None:
        self.scheduler = scheduler
        self._schedule(self.refresh_from_runtime())

    def _schedule(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)
        task.add_done_callback(self._handle_task_result)

    def _handle_task_result(self, task: asyncio.Task[Any]) -> None:
        self._tasks.discard(task)
        try:
            task.result()
        except Exception as exc:
            self.health_view.append("")
            self.health_view.append(f"Error: {exc}")

    async def refresh_from_runtime(self) -> None:
        if self.scheduler is None:
            return
        selected_model = await self.scheduler.get_selected_model()
        if self.model_combo.findText(selected_model) == -1:
            self.model_combo.addItem(selected_model)
        self.model_combo.setCurrentText(selected_model)
        self.autostart_checkbox.setChecked(self.scheduler.is_autostart_enabled())
        health = await self.scheduler.get_backend_status()
        lines = [f"{name}: {state}" for name, state in health.items()]
        self.health_view.setPlainText("\n".join(lines) or "No backend data available.")

    async def save_settings(self) -> None:
        if self.scheduler is None:
            return
        selected = self.model_combo.currentText()
        try:
            await self.scheduler.set_selected_model(selected)
            enabled = await self.scheduler.set_autostart_enabled(
                self.autostart_checkbox.isChecked()
            )
            await self.refresh_from_runtime()
            self.health_view.append("")
            self.health_view.append(f"Saved provider={selected}, startup={enabled}")
        except Exception as exc:
            self.health_view.append("")
            self.health_view.append(f"Save failed: {exc}")
            raise
