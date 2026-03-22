from __future__ import annotations

from collections import deque

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPolygon
from PyQt6.QtWidgets import QLabel, QWidget


class BubbleWidget(QWidget):
    def __init__(self, duration_ms: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.queue: deque[str] = deque()
        self._opacity = 0.0
        self._active = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "color: #111827; background: transparent; padding: 12px; font-size: 12px;"
        )
        self.label.setFixedWidth(220)

        self.fade = QPropertyAnimation(self, b"bubbleOpacity", self)
        self.fade.setDuration(240)
        self.fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade.finished.connect(self._on_animation_finished)

        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self._fade_out)

    def queue_message(self, message: str) -> None:
        trimmed = message.strip()
        if not trimmed:
            return
        if len(trimmed) > 280:
            trimmed = f"{trimmed[:277]}..."
        self.queue.append(trimmed)
        if not self._active:
            self._show_next()

    def _show_next(self) -> None:
        if not self.queue:
            self._active = False
            self.hide()
            return

        self._active = True
        self.label.setText(self.queue.popleft())
        self.label.adjustSize()
        self.resize(self.label.width() + 16, self.label.height() + 24)
        self.label.move(8, 4)
        self._position_above_parent()
        self.show()
        self.raise_()
        self._fade_to(1.0)
        self.dismiss_timer.start(self.duration_ms)

    def _position_above_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(0, (parent.width() - self.width()) // 2)
        y = -self.height() - 10
        self.move(x, y)

    def _fade_to(self, value: float) -> None:
        self.fade.stop()
        self.fade.setStartValue(self._opacity)
        self.fade.setEndValue(value)
        self.fade.start()

    def _fade_out(self) -> None:
        self._fade_to(0.0)

    def _on_animation_finished(self) -> None:
        if self._opacity <= 0.01 and self._active:
            self.hide()
            self._active = False
            self._show_next()

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, value))
        self.update()

    bubbleOpacity = pyqtProperty(float, get_opacity, set_opacity)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        if self._opacity <= 0.0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        fill = QColor("#fff5d6")
        fill.setAlphaF(self._opacity)
        border = QColor("#111827")
        border.setAlphaF(self._opacity)

        bubble_rect = self.rect().adjusted(1, 1, -1, -13)
        painter.setBrush(fill)
        painter.setPen(border)
        painter.drawRoundedRect(bubble_rect, 14, 14)

        center_x = self.width() // 2
        tail = QPolygon(
            [
                QPoint(center_x - 8, bubble_rect.bottom() - 1),
                QPoint(center_x + 8, bubble_rect.bottom() - 1),
                QPoint(center_x, self.height() - 2),
            ]
        )
        painter.drawPolygon(tail)
        painter.end()

