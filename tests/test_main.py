from __future__ import annotations

import os
import shutil
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

pyqt6 = types.ModuleType("PyQt6")
qtcore = types.ModuleType("PyQt6.QtCore")
qtwidgets = types.ModuleType("PyQt6.QtWidgets")
qasync = types.ModuleType("qasync")

qtcore.Qt = types.SimpleNamespace(
    ApplicationAttribute=types.SimpleNamespace(AA_EnableHighDpiScaling=1),
    WindowType=types.SimpleNamespace(
        FramelessWindowHint=1,
        WindowStaysOnTopHint=2,
        Tool=4,
    ),
    WidgetAttribute=types.SimpleNamespace(WA_TranslucentBackground=1),
)
qtwidgets.QApplication = type("QApplication", (), {})
qtwidgets.QLabel = type("QLabel", (), {})
qtwidgets.QVBoxLayout = type("QVBoxLayout", (), {})
qtwidgets.QWidget = type("QWidget", (), {})
qasync.QEventLoop = type("QEventLoop", (), {})

sys.modules.setdefault("PyQt6", pyqt6)
sys.modules.setdefault("PyQt6.QtCore", qtcore)
sys.modules.setdefault("PyQt6.QtWidgets", qtwidgets)
sys.modules.setdefault("qasync", qasync)

import main


class LoadConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests/.tmp_main")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def test_load_config_uses_defaults_when_file_missing(self) -> None:
        config = main.load_config(self.tmp_dir / "missing.yaml")
        self.assertEqual(config["presence"]["idle_threshold_seconds"], 300)
        self.assertEqual(config["ai"]["default_model"], "ollama")

    def test_load_config_merges_partial_overrides(self) -> None:
        config_path = self.tmp_dir / "config.yaml"
        config_path.write_text(
            "presence:\n  idle_threshold_seconds: 120\nai:\n  default_model: groq\n",
            encoding="utf-8",
        )
        config = main.load_config(config_path)

        self.assertEqual(config["presence"]["idle_threshold_seconds"], 120)
        self.assertEqual(config["presence"]["mode_switch_hysteresis"], 2)
        self.assertEqual(config["ai"]["default_model"], "groq")

    def test_load_config_applies_environment_overrides(self) -> None:
        config_path = self.tmp_dir / "config.yaml"
        config_path.write_text(
            "telegram:\n  token: file-token\n  chat_id: file-chat\n",
            encoding="utf-8",
        )

        with mock.patch.dict(
            os.environ,
            {
                "TELEGRAM_BOT_TOKEN": "env-token",
                "TELEGRAM_CHAT_ID": "env-chat",
            },
            clear=False,
        ):
            config = main.load_config(config_path)

        self.assertEqual(config["telegram"]["token"], "env-token")
        self.assertEqual(config["telegram"]["chat_id"], "env-chat")


if __name__ == "__main__":
    unittest.main()
