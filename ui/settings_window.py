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

        self.setWindowTitle("Companion Settings")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(420, 360)
        self.setStyleSheet(
            "background: rgba(8, 12, 24, 245); color: #e5e7eb;"
            "QComboBox, QTextEdit { background: rgba(15, 23, 42, 255); color: #f8fafc; }"
            "QPushButton { background: rgba(59, 130, 246, 210); color: white; padding: 8px 12px; border-radius: 8px; }"
            "QCheckBox { spacing: 8px; }"
        )

        self.model_combo = QComboBox()
        self.model_combo.addItems(["ollama", "groq", "gemini"])

        self.autostart_checkbox = QCheckBox("Launch companion when Windows starts")
        self.health_view = QTextEdit()
        self.health_view.setReadOnly(True)
        self.health_view.setPlaceholderText("Backend health will appear here...")

        form = QFormLayout()
        form.addRow("Active model", self.model_combo)
        form.addRow("Autostart", self.autostart_checkbox)

        self.refresh_button = QPushButton("Refresh Health")
        self.refresh_button.clicked.connect(lambda: self._schedule(self.refresh_from_runtime()))
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(lambda: self._schedule(self.save_settings()))

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Backend health"))
        layout.addWidget(self.health_view, 1)
        layout.addLayout(buttons)

    def bind_scheduler(self, scheduler: Any) -> None:
        self.scheduler = scheduler
        self._schedule(self.refresh_from_runtime())

    def _schedule(self, coroutine) -> None:
        asyncio.create_task(coroutine)

    async def refresh_from_runtime(self) -> None:
        if self.scheduler is None:
            return
        selected_model = await self.scheduler.get_selected_model()
        self.model_combo.setCurrentText(selected_model)
        self.autostart_checkbox.setChecked(self.scheduler.is_autostart_enabled())
        health = await self.scheduler.get_backend_status()
        lines = [f"{name}: {state}" for name, state in health.items()]
        self.health_view.setPlainText("\n".join(lines) or "No backend data available.")

    async def save_settings(self) -> None:
        if self.scheduler is None:
            return
        selected = self.model_combo.currentText()
        await self.scheduler.set_selected_model(selected)
        enabled = await self.scheduler.set_autostart_enabled(self.autostart_checkbox.isChecked())
        await self.refresh_from_runtime()
        self.health_view.append("")
        self.health_view.append(f"Saved model={selected}, autostart={enabled}")
