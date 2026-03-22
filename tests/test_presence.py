from __future__ import annotations

import unittest
from unittest import mock

from core.presence import PresenceDetector


def build_config() -> dict:
    return {
        "presence": {
            "idle_threshold_seconds": 300,
            "mode_switch_hysteresis": 2,
        }
    }


class FakePresenceDetector(PresenceDetector):
    def __init__(self, config: dict, idle_values: list[int]) -> None:
        super().__init__(config)
        self.idle_values = idle_values

    def _get_system_idle_milliseconds(self) -> int:
        return self.idle_values.pop(0)


class PresenceDetectorTests(unittest.TestCase):
    def test_user_present_below_threshold(self) -> None:
        detector = FakePresenceDetector(build_config(), [1000])
        self.assertTrue(detector.is_user_present())

    def test_hysteresis_requires_consecutive_remote_checks(self) -> None:
        detector = FakePresenceDetector(
            build_config(),
            [301000, 301000, 1000],
        )

        self.assertEqual(detector.evaluate_mode(), ("local", False))
        self.assertEqual(detector.evaluate_mode(), ("remote", True))
        self.assertEqual(detector.get_mode(), "remote")
        self.assertEqual(detector.evaluate_mode(), ("local", True))

    def test_return_to_local_is_immediate_after_remote(self) -> None:
        detector = FakePresenceDetector(
            build_config(),
            [301000, 301000, 1000],
        )

        detector.evaluate_mode()
        detector.evaluate_mode()
        self.assertEqual(detector.get_mode(), "remote")
        self.assertEqual(detector.evaluate_mode(), ("local", True))
        self.assertEqual(detector.get_mode(), "local")

    def test_synthetic_keepalive_does_not_reset_effective_idle(self) -> None:
        detector = FakePresenceDetector(build_config(), [1000, 500])

        with mock.patch("core.presence.time.monotonic", side_effect=[100.0, 101.0, 106.5]):
            detector.mark_synthetic_input(240000)
            self.assertEqual(detector.get_idle_milliseconds(), 241000)
            self.assertEqual(detector.get_idle_milliseconds(), 500)


if __name__ == "__main__":
    unittest.main()
