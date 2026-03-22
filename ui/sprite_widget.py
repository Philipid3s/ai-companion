from __future__ import annotations

import logging
import random
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget


class SpriteWidget(QLabel):
    def __init__(self, assets_dir: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.assets_dir = assets_dir
        self.logger = logging.getLogger("ui.sprite")
        self.frame_size = 76
        self.state_frames = {
            "idle": [":)", "^_^"],
            "alert": ["!", "!!"],
            "remote": ["R", "Zz"],
            "thinking": ["?", "..."],
        }
        self.state = "idle"
        self.frame_index = 0
        self.frames = self._load_frames()

        self.setFixedSize(self.frame_size + 8, self.frame_size + 8)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: 0;")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.advance_frame)
        self.set_state("idle")

    def _load_frames(self) -> dict[str, list[QPixmap]]:
        frames: dict[str, list[QPixmap]] = {}
        sprite_root = self.assets_dir / "sprites"
        self.logger.info("Loading sprites from %s", sprite_root)
        for state, fallback_symbols in self.state_frames.items():
            state_dir = sprite_root / state
            pixmaps: list[QPixmap] = []
            for file_path in self._iter_state_frame_paths(state_dir, state):
                pixmap = QPixmap(str(file_path))
                if pixmap.isNull():
                    self.logger.warning("Failed to load sprite frame: %s", file_path)
                    continue
                pixmaps.append(
                    pixmap.scaled(
                        self.frame_size,
                        self.frame_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                )
            if not pixmaps:
                self.logger.warning("Using placeholder sprites for state=%s", state)
                pixmaps = [self._placeholder_frame(state, symbol) for symbol in fallback_symbols]
            frames[state] = pixmaps
        return frames

    def _iter_state_frame_paths(self, state_dir: Path, state: str) -> list[Path]:
        if not state_dir.exists():
            self.logger.warning("Sprite state directory missing: %s", state_dir)
            return []

        pngs = sorted(path for path in state_dir.rglob("*.png") if path.is_file())
        if not pngs:
            self.logger.warning("No sprite frames found in: %s", state_dir)
            return []

        prefixed = [path for path in pngs if path.stem.lower().startswith(f"{state}_")]
        return prefixed or pngs

    def _placeholder_frame(self, state: str, symbol: str) -> QPixmap:
        palette = {
            "idle": QColor("#62d2a2"),
            "alert": QColor("#ff8f70"),
            "remote": QColor("#6b7280"),
            "thinking": QColor("#7cc6fe"),
        }
        pixmap = QPixmap(self.frame_size, self.frame_size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(palette.get(state, QColor("#62d2a2")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.frame_size, self.frame_size, 14, 14)
        painter.setPen(QColor("#111827"))
        font = painter.font()
        font.setPointSize(28)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, symbol)
        painter.end()
        return pixmap

    def set_state(self, state: str) -> None:
        if state not in self.frames:
            state = "idle"
        self.state = state
        self.frame_index = 0
        self._render_current_frame()
        self._timer.start(self._next_interval_ms())

    def advance_frame(self) -> None:
        state_frames = self.frames[self.state]
        if len(state_frames) <= 1:
            self.frame_index = 0
        else:
            self.frame_index = 1 if self.frame_index == 0 else 0
        self._render_current_frame()
        self._timer.start(self._next_interval_ms())

    def _next_interval_ms(self) -> int:
        if self.frame_index == 0:
            return random.randint(4000, 10000)
        return random.randint(2000, 4000)

    def _render_current_frame(self) -> None:
        self.setPixmap(self.frames[self.state][self.frame_index])
