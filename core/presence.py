from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from typing import Literal


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class PresenceDetector:
    def __init__(self, config: dict) -> None:
        presence_config = config["presence"]
        self.idle_threshold_seconds = int(presence_config["idle_threshold_seconds"])
        self.hysteresis_required = max(1, int(presence_config["mode_switch_hysteresis"]))
        self._mode: Literal["local", "remote"] = "local"
        self._pending_mode: Literal["local", "remote"] | None = None
        self._pending_count = 0
        self._user32 = getattr(ctypes, "windll", None)
        self._synthetic_idle_baseline_ms = 0
        self._synthetic_input_started_at: float | None = None
        self._synthetic_reset_tolerance_ms = 1500

    def _get_system_idle_milliseconds(self) -> int:
        if self._user32 is None:
            return 0

        user32 = self._user32.user32
        kernel32 = self._user32.kernel32
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            raise ctypes.WinError()
        tick_count = kernel32.GetTickCount()
        return max(0, int(tick_count - info.dwTime))

    def get_idle_milliseconds(self) -> int:
        system_idle_ms = self._get_system_idle_milliseconds()
        if self._synthetic_input_started_at is None:
            return system_idle_ms

        elapsed_since_synthetic_ms = int(
            (time.monotonic() - self._synthetic_input_started_at) * 1000
        )
        if system_idle_ms + self._synthetic_reset_tolerance_ms < elapsed_since_synthetic_ms:
            self._clear_synthetic_input()
            return system_idle_ms

        return max(
            system_idle_ms,
            self._synthetic_idle_baseline_ms + elapsed_since_synthetic_ms,
        )

    def mark_synthetic_input(self, observed_idle_ms: int | None = None) -> None:
        if observed_idle_ms is None:
            observed_idle_ms = self.get_idle_milliseconds()
        self._synthetic_idle_baseline_ms = max(0, int(observed_idle_ms))
        self._synthetic_input_started_at = time.monotonic()

    def _clear_synthetic_input(self) -> None:
        self._synthetic_idle_baseline_ms = 0
        self._synthetic_input_started_at = None

    def is_user_present(self) -> bool:
        return self.get_idle_milliseconds() < (self.idle_threshold_seconds * 1000)

    def evaluate_mode(self) -> tuple[Literal["local", "remote"], bool]:
        candidate: Literal["local", "remote"] = (
            "local" if self.is_user_present() else "remote"
        )
        if candidate == self._mode:
            self._pending_mode = None
            self._pending_count = 0
            return self._mode, False

        if self._mode == "remote" and candidate == "local":
            self._mode = "local"
            self._pending_mode = None
            self._pending_count = 0
            return self._mode, True

        if candidate != self._pending_mode:
            self._pending_mode = candidate
            self._pending_count = 1
            return self._mode, False

        self._pending_count += 1
        if self._pending_count >= self.hysteresis_required:
            self._mode = candidate
            self._pending_mode = None
            self._pending_count = 0
            return self._mode, True

        return self._mode, False

    def get_mode(self) -> Literal["local", "remote"]:
        return self._mode
