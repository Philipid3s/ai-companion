from __future__ import annotations

import importlib
import sys
import types
import unittest

pyqt6 = types.ModuleType("PyQt6")
qtcore = types.ModuleType("PyQt6.QtCore")
qtwidgets = types.ModuleType("PyQt6.QtWidgets")


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)


class FakeWidget:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.object_name = ""

    def setWindowTitle(self, _title: str) -> None:
        return None

    def setWindowFlags(self, _flags) -> None:
        return None

    def resize(self, _width: int, _height: int) -> None:
        return None

    def setStyleSheet(self, _stylesheet: str) -> None:
        return None

    def setObjectName(self, name: str) -> None:
        self.object_name = name


class FakeCheckBox:
    def __init__(self, _label: str = "") -> None:
        self.checked = False

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def isChecked(self) -> bool:
        return self.checked


class FakeComboBox:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.current = ""

    def addItems(self, items: list[str]) -> None:
        self.items.extend(items)
        if not self.current and self.items:
            self.current = self.items[0]

    def addItem(self, item: str) -> None:
        self.items.append(item)

    def setCurrentText(self, value: str) -> None:
        if value in self.items:
            self.current = value

    def currentText(self) -> str:
        return self.current

    def findText(self, value: str) -> int:
        try:
            return self.items.index(value)
        except ValueError:
            return -1


class FakeTextEdit:
    def __init__(self) -> None:
        self.text = ""

    def setReadOnly(self, _value: bool) -> None:
        return None

    def setPlaceholderText(self, _value: str) -> None:
        return None

    def setPlainText(self, value: str) -> None:
        self.text = value

    def append(self, value: str) -> None:
        self.text = f"{self.text}\n{value}" if self.text else value


class FakePushButton:
    def __init__(self, _label: str) -> None:
        self.clicked = FakeSignal()


class FakeLayout:
    def __init__(self, *_args, **_kwargs) -> None:
        return None

    def addRow(self, *_args) -> None:
        return None

    def addWidget(self, *_args) -> None:
        return None

    def addLayout(self, *_args) -> None:
        return None

    def addSpacing(self, *_args) -> None:
        return None

    def setContentsMargins(self, *_args) -> None:
        return None

    def setSpacing(self, *_args) -> None:
        return None


qtcore.Qt = types.SimpleNamespace(
    WindowType=types.SimpleNamespace(Tool=1, WindowStaysOnTopHint=2),
)
qtwidgets.QCheckBox = FakeCheckBox
qtwidgets.QComboBox = FakeComboBox
qtwidgets.QFormLayout = FakeLayout
qtwidgets.QHBoxLayout = FakeLayout
qtwidgets.QLabel = type(
    "QLabel",
    (FakeWidget,),
    {"__init__": lambda self, *_args, **_kwargs: FakeWidget.__init__(self)},
)
qtwidgets.QPushButton = FakePushButton
qtwidgets.QTextEdit = FakeTextEdit
qtwidgets.QVBoxLayout = FakeLayout
qtwidgets.QWidget = FakeWidget

sys.modules["PyQt6"] = pyqt6
sys.modules["PyQt6.QtCore"] = qtcore
sys.modules["PyQt6.QtWidgets"] = qtwidgets
sys.modules.pop("ui.settings_window", None)

settings_window = importlib.import_module("ui.settings_window")
SettingsWindow = settings_window.SettingsWindow


class FakeScheduler:
    def __init__(self, model: str = "groq", autostart: bool = True) -> None:
        self.model = model
        self.autostart = autostart
        self.set_model_calls: list[str] = []
        self.set_autostart_calls: list[bool] = []

    async def get_selected_model(self) -> str:
        return self.model

    def is_autostart_enabled(self) -> bool:
        return self.autostart

    async def get_backend_status(self) -> dict[str, str]:
        return {"ollama": "available", "groq": "unavailable"}

    async def set_selected_model(self, model: str) -> str:
        self.set_model_calls.append(model)
        self.model = model
        return model

    async def set_autostart_enabled(self, enabled: bool) -> bool:
        self.set_autostart_calls.append(enabled)
        self.autostart = enabled
        return enabled


class SettingsWindowTests(unittest.IsolatedAsyncioTestCase):
    def build_window(self) -> SettingsWindow:
        return SettingsWindow(config={})

    async def test_refresh_populates_fields_from_scheduler(self) -> None:
        window = self.build_window()
        window.scheduler = FakeScheduler()

        await window.refresh_from_runtime()

        self.assertEqual(window.model_combo.currentText(), "groq")
        self.assertTrue(window.autostart_checkbox.isChecked())
        self.assertIn("ollama: available", window.health_view.text)

    async def test_refresh_adds_unknown_selected_model(self) -> None:
        window = self.build_window()
        window.scheduler = FakeScheduler(model="custom-backend")

        await window.refresh_from_runtime()

        self.assertIn("custom-backend", window.model_combo.items)
        self.assertEqual(window.model_combo.currentText(), "custom-backend")

    async def test_save_settings_persists_values_and_appends_status(self) -> None:
        window = self.build_window()
        scheduler = FakeScheduler(model="ollama", autostart=False)
        window.scheduler = scheduler
        window.model_combo.setCurrentText("gemini")
        window.autostart_checkbox.setChecked(True)

        await window.save_settings()

        self.assertEqual(scheduler.set_model_calls, ["gemini"])
        self.assertEqual(scheduler.set_autostart_calls, [True])
        self.assertIn("Saved provider=gemini, startup=True", window.health_view.text)


if __name__ == "__main__":
    unittest.main()
