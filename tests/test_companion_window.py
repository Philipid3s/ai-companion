from __future__ import annotations

import importlib
import sys
import types
import unittest

pyqt6 = types.ModuleType("PyQt6")
qtcore = types.ModuleType("PyQt6.QtCore")
qtgui = types.ModuleType("PyQt6.QtGui")
qtwidgets = types.ModuleType("PyQt6.QtWidgets")


class FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)


class FakePoint:
    def __init__(self, x: int = 0, y: int = 0) -> None:
        self._x = x
        self._y = y

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def __sub__(self, other: "FakePoint") -> "FakePoint":
        return FakePoint(self._x - other._x, self._y - other._y)

    def manhattanLength(self) -> int:
        return abs(self._x) + abs(self._y)


class FakeRect:
    def right(self) -> int:
        return 799

    def bottom(self) -> int:
        return 599

    def left(self) -> int:
        return 0

    def top(self) -> int:
        return 0


class FakeScreen:
    def availableGeometry(self) -> FakeRect:
        return FakeRect()


class FakeWidget:
    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._width = 100
        self._height = 100
        self.tooltip = ""
        self.pos = FakePoint(0, 0)

    def setWindowTitle(self, _title: str) -> None:
        return None

    def setWindowFlags(self, _flags) -> None:
        return None

    def setAttribute(self, _attr, _value=True) -> None:
        return None

    def resize(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def move(self, x, y=None) -> None:
        if isinstance(x, FakePoint):
            self.pos = x
        else:
            self.pos = FakePoint(int(x), int(y))

    def update(self) -> None:
        return None

    def setToolTip(self, text: str) -> None:
        self.tooltip = text

    def show(self) -> None:
        return None

    def close(self) -> None:
        return None

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None

    def frameGeometry(self):
        return types.SimpleNamespace(topLeft=lambda: FakePoint(0, 0))

    def screen(self):
        return FakeScreen()

    def window(self):
        return self

    def mapToGlobal(self, point: FakePoint) -> FakePoint:
        return point

    def parentWidget(self):
        return self._parent

    def mousePressEvent(self, _event) -> None:
        return None

    def mouseMoveEvent(self, _event) -> None:
        return None

    def mouseReleaseEvent(self, _event) -> None:
        return None


class FakeApplication:
    @staticmethod
    def primaryScreen() -> FakeScreen:
        return FakeScreen()

    @staticmethod
    def instance():
        return types.SimpleNamespace(quit=lambda: None)


class FakeTimer:
    def __init__(self, _parent=None) -> None:
        self.timeout = FakeSignal()
        self.started_with: list[int] = []

    def start(self, interval: int) -> None:
        self.started_with.append(interval)

    @staticmethod
    def singleShot(_interval: int, _callback) -> None:
        return None


qtcore.QPoint = FakePoint
qtcore.QRectF = type("QRectF", (), {})
qtcore.QTimer = FakeTimer
qtcore.Qt = types.SimpleNamespace(
    WindowType=types.SimpleNamespace(FramelessWindowHint=1, WindowStaysOnTopHint=2, Tool=4),
    WidgetAttribute=types.SimpleNamespace(WA_TranslucentBackground=1),
    MouseButton=types.SimpleNamespace(LeftButton=1, RightButton=2),
    PenStyle=types.SimpleNamespace(NoPen=0),
)
qtgui.QAction = type("QAction", (), {"__init__": lambda self, *_args, **_kwargs: setattr(self, "triggered", FakeSignal())})
qtgui.QColor = type("QColor", (), {"__init__": lambda self, *_args, **_kwargs: None})
qtgui.QCursor = type("QCursor", (), {"pos": staticmethod(lambda: FakePoint())})
qtgui.QPainter = type("QPainter", (), {"__init__": lambda self, *_args, **_kwargs: None})
qtwidgets.QApplication = FakeApplication
qtwidgets.QLabel = type("QLabel", (), {})
qtwidgets.QVBoxLayout = type("QVBoxLayout", (), {"__init__": lambda self, *_args, **_kwargs: None, "addWidget": lambda self, *_args, **_kwargs: None})
qtwidgets.QMenu = type("QMenu", (), {"__init__": lambda self, *_args, **_kwargs: None, "addAction": lambda self, *_args, **_kwargs: None, "addSeparator": lambda self: None, "exec": lambda self, *_args, **_kwargs: None})
qtwidgets.QWidget = FakeWidget

sys.modules["PyQt6"] = pyqt6
sys.modules["PyQt6.QtCore"] = qtcore
sys.modules["PyQt6.QtGui"] = qtgui
sys.modules["PyQt6.QtWidgets"] = qtwidgets


class FakeBubbleWidget:
    def __init__(self, duration_ms: int, parent=None) -> None:
        self.duration_ms = duration_ms
        self.parent = parent
        self.messages: list[str] = []

    def queue_message(self, message: str) -> None:
        self.messages.append(message)


class FakeCLIPanel:
    def __init__(self, config: dict, parent=None) -> None:
        self.config = config
        self.parent = parent
        self.command_handler = None
        self.output: list[str] = []

    def set_command_handler(self, handler) -> None:
        self.command_handler = handler

    def append_output(self, message: str) -> None:
        self.output.append(message)

    def sync_to_parent(self) -> None:
        return None

    def toggle(self) -> None:
        return None


class FakeSettingsWindow:
    def __init__(self, config: dict, parent=None) -> None:
        self.config = config
        self.parent = parent
        self.bound_scheduler = None
        self.refresh_calls = 0

    def bind_scheduler(self, scheduler) -> None:
        self.bound_scheduler = scheduler

    async def refresh_from_runtime(self) -> None:
        self.refresh_calls += 1

    def show(self) -> None:
        return None

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None


class FakeSpriteWidget:
    def __init__(self, assets_dir, parent=None) -> None:
        self.assets_dir = assets_dir
        self.parent = parent
        self.state = "idle"
        self.state_history = ["idle"]
        self.pos = FakePoint(0, 0)

    def move(self, x: int, y: int) -> None:
        self.pos = FakePoint(x, y)

    def set_state(self, state: str) -> None:
        self.state = state
        self.state_history.append(state)


bubble_module = types.ModuleType("ui.bubble_widget")
bubble_module.BubbleWidget = FakeBubbleWidget
cli_module = types.ModuleType("ui.cli_panel")
cli_module.CLIPanel = FakeCLIPanel
settings_module = types.ModuleType("ui.settings_window")
settings_module.SettingsWindow = FakeSettingsWindow
sprite_module = types.ModuleType("ui.sprite_widget")
sprite_module.SpriteWidget = FakeSpriteWidget

sys.modules["ui.bubble_widget"] = bubble_module
sys.modules["ui.cli_panel"] = cli_module
sys.modules["ui.settings_window"] = settings_module
sys.modules["ui.sprite_widget"] = sprite_module
sys.modules.pop("ui.companion_window", None)

companion_window = importlib.import_module("ui.companion_window")
CompanionWindow = companion_window.CompanionWindow


class FakePresenceDetector:
    def __init__(self, mode: str = "local") -> None:
        self.mode = mode

    def get_mode(self) -> str:
        return self.mode


class FakeScheduler:
    def __init__(self) -> None:
        self.ui_notifier = None
        self.ui_state_notifier = None

    def set_ui_notifier(self, notifier) -> None:
        self.ui_notifier = notifier

    def set_ui_state_notifier(self, notifier) -> None:
        self.ui_state_notifier = notifier


class CompanionWindowTests(unittest.TestCase):
    def build_window(self, mode: str = "local") -> CompanionWindow:
        return CompanionWindow(
            config={"ui": {"bubble_duration_ms": 6000, "margin_px": 20}},
            presence_detector=FakePresenceDetector(mode),
        )

    def test_refresh_ui_uses_remote_state_when_not_thinking(self) -> None:
        window = self.build_window(mode="remote")
        window.sprite.state = "idle"

        window.refresh_ui()

        self.assertEqual(window.sprite.state, "remote")
        self.assertIn("Mode: remote", window.tooltip)

    def test_refresh_ui_preserves_thinking_state(self) -> None:
        window = self.build_window(mode="remote")
        window.sprite.state = "thinking"
        before = list(window.sprite.state_history)

        window.refresh_ui()

        self.assertEqual(window.sprite.state, "thinking")
        self.assertEqual(window.sprite.state_history, before)

    def test_show_message_only_queues_bubble_when_local(self) -> None:
        local_window = self.build_window(mode="local")
        local_window.show_message("hello", "idle")
        self.assertEqual(local_window.bubble.messages, ["hello"])
        self.assertIn("hello", local_window.cli_panel.output)

        remote_window = self.build_window(mode="remote")
        remote_window.show_message("remote hello", "remote")
        self.assertEqual(remote_window.bubble.messages, [])
        self.assertIn("remote hello", remote_window.cli_panel.output)

    def test_bind_scheduler_registers_ui_notifiers(self) -> None:
        window = self.build_window(mode="local")
        scheduler = FakeScheduler()
        scheduled: list = []

        def capture(coro) -> None:
            scheduled.append(coro)

        window._schedule_coroutine = capture
        try:
            window.bind_scheduler(scheduler)
            self.assertIs(scheduler.ui_notifier.__self__, window)
            self.assertIs(scheduler.ui_notifier.__func__, window.show_message.__func__)
            self.assertIs(scheduler.ui_state_notifier.__self__, window)
            self.assertIs(scheduler.ui_state_notifier.__func__, window.set_sprite_state.__func__)
            self.assertIs(window.settings_window.bound_scheduler, scheduler)
            self.assertEqual(len(scheduled), 1)
        finally:
            for coro in scheduled:
                coro.close()

    def test_set_sprite_state_updates_sprite_directly(self) -> None:
        window = self.build_window(mode="local")

        window.set_sprite_state("thinking")

        self.assertEqual(window.sprite.state, "thinking")
        self.assertIn("thinking", window.sprite.state_history)


if __name__ == "__main__":
    unittest.main()
