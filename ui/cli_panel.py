from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QWidget


class HistoryLineEdit(QLineEdit):
    def __init__(self, owner, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.owner = owner

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Up:
            self.owner.show_previous_history()
            return
        if event.key() == Qt.Key.Key_Down:
            self.owner.show_next_history()
            return
        super().keyPressEvent(event)


class CLIPanel(QWidget):
    def __init__(self, config: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.command_handler = None
        self.command_history: list[str] = []
        self.history_index = 0

        self.setWindowTitle("Companion Console")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.resize(760, 460)

        shell = QFrame(self)
        shell.setObjectName("shell")
        shell.setStyleSheet(
            "QFrame#shell {"
            "background: rgba(3, 7, 18, 242);"
            "border: 1px solid rgba(148, 163, 184, 0.32);"
            "border-radius: 18px;"
            "}"
            "QLabel { color: #dbe4ff; }"
            "QTextEdit {"
            "background: rgba(2, 6, 23, 235);"
            "border: 1px solid rgba(124, 198, 254, 0.16);"
            "border-radius: 12px;"
            "color: #d1fae5;"
            "padding: 10px;"
            "selection-background-color: rgba(124, 198, 254, 0.35);"
            "}"
            "QLineEdit {"
            "background: rgba(15, 23, 42, 255);"
            "border: 1px solid rgba(148, 163, 184, 0.24);"
            "border-radius: 10px;"
            "color: #f8fafc;"
            "padding: 10px 12px;"
            "}"
        )

        title = QLabel("COMPANION TERMINAL")
        title_font = QFont("Consolas", 11)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("status | processes | model <name> | memory | note <text> | ask <prompt>")
        subtitle.setStyleSheet("color: rgba(226, 232, 240, 0.72);")
        subtitle.setWordWrap(True)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        mono = QFont("Consolas", 10)
        self.output.setFont(mono)
        self.output.setPlaceholderText("Companion logs and command output...")

        prompt_label = QLabel(">")
        prompt_label.setFont(QFont("Consolas", 13, weight=QFont.Weight.Bold))
        prompt_label.setStyleSheet("color: #7dd3fc;")

        self.input = HistoryLineEdit(self)
        self.input.setFont(mono)
        self.input.setPlaceholderText("Enter a command and press Enter")
        self.input.returnPressed.connect(self._submit)

        input_row = QHBoxLayout()
        input_row.setSpacing(10)
        input_row.addWidget(prompt_label)
        input_row.addWidget(self.input, 1)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(12)
        shell_layout.addWidget(title)
        shell_layout.addWidget(subtitle)
        shell_layout.addWidget(self.output, 1)
        shell_layout.addLayout(input_row)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(shell)

        self.hide()

    def set_command_handler(self, handler) -> None:
        self.command_handler = handler

    def append_output(self, message: str) -> None:
        self.output.append(message)
        self.output.moveCursor(self.output.textCursor().MoveOperation.End)

    def toggle(self) -> None:
        if self.isVisible():
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self) -> None:
        self.sync_to_parent()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def close_panel(self) -> None:
        self.hide()

    def _submit(self) -> None:
        command = self.input.text().strip()
        if not command:
            return
        self.command_history.append(command)
        self.history_index = len(self.command_history)
        self.append_output(f"> {command}")
        self.input.clear()
        if self.command_handler is not None:
            result = self.command_handler(command)
            if result:
                self.append_output(result)

    def show_previous_history(self) -> None:
        if not self.command_history:
            return
        self.history_index = max(0, self.history_index - 1)
        self.input.setText(self.command_history[self.history_index])

    def show_next_history(self) -> None:
        if not self.command_history:
            return
        self.history_index = min(len(self.command_history), self.history_index + 1)
        if self.history_index == len(self.command_history):
            self.input.clear()
            return
        self.input.setText(self.command_history[self.history_index])

    def sync_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        anchor = parent.mapToGlobal(QPoint(0, 0))
        x = anchor.x() - self.width() - 24
        y = anchor.y() - self.height() + parent.height() + 12
        screen = parent.screen() or parent.window().screen()
        if screen is not None:
            geometry = screen.availableGeometry()
            if x < geometry.left() + 12:
                x = anchor.x() + parent.width() + 16
            x = max(geometry.left() + 12, min(x, geometry.right() - self.width() - 12))
            y = max(geometry.top() + 12, min(y, geometry.bottom() - self.height() - 12))
        self.move(x, y)
