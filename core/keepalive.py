from __future__ import annotations

import ctypes
import logging
import math
import random
import secrets
from ctypes import wintypes


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUT_UNION),
    ]


class KeepAliveService:
    def __init__(self, config: dict) -> None:
        keepalive_config = config["keepalive"]
        self.min_interval_seconds = int(keepalive_config["min_interval_seconds"])
        self.max_interval_seconds = int(keepalive_config["max_interval_seconds"])
        self.mouse_delta_max_px = max(1, int(keepalive_config["mouse_delta_max_px"]))
        self.logger = logging.getLogger("core.keepalive")
        self._windll = getattr(ctypes, "windll", None)

    def enable_execution_state(self) -> None:
        if self._windll is None:
            self.logger.warning("Execution state API unavailable on this platform")
            return

        result = self._windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
        )
        if result == 0:
            raise ctypes.WinError()

    def next_interval_seconds(self) -> int:
        span = self.max_interval_seconds - self.min_interval_seconds + 1
        return self.min_interval_seconds + secrets.randbelow(max(1, span))

    def _random_delta(self) -> int:
        delta = int(round(random.gauss(0, self.mouse_delta_max_px / 2)))
        delta = max(-self.mouse_delta_max_px, min(self.mouse_delta_max_px, delta))
        if delta == 0:
            delta = 1 if secrets.randbelow(2) == 0 else -1
        return delta

    def send_mouse_jitter(self) -> tuple[int, int]:
        if self._windll is None:
            self.logger.warning("SendInput unavailable on this platform")
            return (0, 0)

        dx = self._random_delta()
        dy = self._random_delta()
        if abs(dx) == abs(dy):
            dy = int(math.copysign(max(1, abs(dy) - 1), dy))

        input_struct = INPUT(
            type=INPUT_MOUSE,
            mi=MOUSEINPUT(
                dx=dx,
                dy=dy,
                mouseData=0,
                dwFlags=MOUSEEVENTF_MOVE,
                time=0,
                dwExtraInfo=0,
            ),
        )
        sent = self._windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(INPUT))
        if sent != 1:
            raise ctypes.WinError()
        self.logger.info("Sent keepalive mouse jitter dx=%s dy=%s", dx, dy)
        return (dx, dy)
