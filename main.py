from __future__ import annotations

import asyncio
import importlib
import logging
import os
import signal
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from qasync import QEventLoop

from paths import CONFIG_PATH, RUNTIME_DIR


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG: dict[str, Any] = {
    "telegram": {"token": "", "chat_id": ""},
    "presence": {
        "idle_threshold_seconds": 300,
        "mode_switch_hysteresis": 2,
    },
    "keepalive": {
        "min_interval_seconds": 180,
        "max_interval_seconds": 420,
        "mouse_delta_max_px": 3,
    },
    "monitoring": {
        "cpu_alert_threshold": 85,
        "ram_alert_threshold": 90,
        "check_interval_seconds": 30,
    },
    "ai": {
        "default_model": "ollama",
        "ollama_url": "http://localhost:11434",
        "ollama_model": "qwen3:8b",
        "gemini_api_key": "",
        "groq_api_key": "",
        "fallback_order": ["ollama", "groq", "gemini"],
    },
    "ui": {
        "sprite": "default",
        "position": "bottom-right",
        "margin_px": 20,
        "bubble_duration_ms": 6000,
    },
}


def configure_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(RUNTIME_DIR / "companion.log", encoding="utf-8")
        handlers.append(file_handler)
    except OSError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def configure_qt_attributes() -> None:
    app_attr = getattr(Qt, "ApplicationAttribute", None)
    if app_attr is None:
        return
    high_dpi_attr = getattr(app_attr, "AA_EnableHighDpiScaling", None)
    if high_dpi_attr is not None:
        QApplication.setAttribute(high_dpi_attr, True)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def apply_environment_overrides(config: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(config)
    env_mappings = {
        ("telegram", "token"): "TELEGRAM_BOT_TOKEN",
        ("telegram", "chat_id"): "TELEGRAM_CHAT_ID",
        ("ai", "gemini_api_key"): "GEMINI_API_KEY",
        ("ai", "groq_api_key"): "GROQ_API_KEY",
        ("ai", "ollama_url"): "OLLAMA_URL",
    }
    for path, env_name in env_mappings.items():
        value = os.getenv(env_name)
        if not value:
            continue
        node = merged
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
    return merged


def load_config(config_path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        logging.warning("config.yaml not found at %s; using defaults", config_path)
        return apply_environment_overrides(deepcopy(DEFAULT_CONFIG))

    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    if not isinstance(raw_config, dict):
        raise ValueError("config.yaml must contain a top-level mapping")

    return apply_environment_overrides(deep_merge(DEFAULT_CONFIG, raw_config))


class BootstrapPresenceDetector:
    def __init__(self, config: dict[str, Any]) -> None:
        self.idle_threshold_seconds = int(
            config["presence"]["idle_threshold_seconds"]
        )
        self._mode = "local"

    def is_user_present(self) -> bool:
        return True

    def get_mode(self) -> str:
        return self._mode


class BootstrapScheduler:
    def __init__(self, config: dict[str, Any], presence_detector: Any, **_: Any) -> None:
        self.config = config
        self.presence_detector = presence_detector
        self.logger = logging.getLogger("bootstrap.scheduler")

    def start(self) -> None:
        self.logger.info("Scheduler fallback active; background jobs are not registered")

    def set_ui_notifier(self, _notifier) -> None:
        return None

    def set_ui_state_notifier(self, _notifier) -> None:
        return None

    async def shutdown(self) -> None:
        self.logger.info("Scheduler fallback shutdown complete")


class BootstrapCompanionWindow(QWidget):
    def __init__(self, config: dict[str, Any], presence_detector: Any, **_: Any) -> None:
        super().__init__()
        self.config = config
        self.presence_detector = presence_detector
        self.setWindowTitle("AI Windows Companion")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        label = QLabel("AI Companion bootstrap window")
        label.setStyleSheet(
            "background: rgba(30, 30, 30, 180); color: white; padding: 12px; "
            "border-radius: 10px;"
        )
        layout.addWidget(label)
        self.resize(260, 72)

    def bind_scheduler(self, _scheduler: Any) -> None:
        return None


def resolve_component(module_name: str, class_name: str, fallback: type[Any]) -> type[Any]:
    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logging.getLogger("bootstrap").exception(
            "Using fallback for %s.%s", module_name, class_name, exc_info=exc
        )
        return fallback


async def run() -> int:
    config = load_config()

    PresenceDetector = resolve_component(
        "core.presence", "PresenceDetector", BootstrapPresenceDetector
    )
    SchedulerService = resolve_component(
        "core.scheduler", "CompanionScheduler", BootstrapScheduler
    )
    CompanionWindow = resolve_component(
        "ui.companion_window", "CompanionWindow", BootstrapCompanionWindow
    )

    presence_detector = PresenceDetector(config)
    window = CompanionWindow(config=config, presence_detector=presence_detector)
    scheduler = SchedulerService(config=config, presence_detector=presence_detector)
    if hasattr(window, "bind_scheduler"):
        window.bind_scheduler(scheduler)
    scheduler.start()
    window.show()

    stop_event = asyncio.Event()

    def request_shutdown() -> None:
        if not stop_event.is_set():
            logging.getLogger("main").info("Shutdown requested")
            stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown)
        except NotImplementedError:
            signal.signal(sig, lambda *_args: request_shutdown())

    app = QApplication.instance()
    assert app is not None
    app.aboutToQuit.connect(request_shutdown)

    try:
        await stop_event.wait()
    finally:
        await scheduler.shutdown()
        window.close()

    return 0


def main() -> int:
    configure_logging()
    configure_qt_attributes()
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        return loop.run_until_complete(run())


if __name__ == "__main__":
    raise SystemExit(main())

