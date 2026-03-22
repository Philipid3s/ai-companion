from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only feature
    winreg = None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AIWindowsCompanion"


def _command(app_path: Path | None = None) -> str:
    target = app_path or Path(__file__).resolve().parents[1] / "main.py"
    return f'"{sys.executable}" "{target}"'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool, app_path: Path | None = None) -> bool:
    if winreg is None:
        return False
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command(app_path))
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    return enabled
