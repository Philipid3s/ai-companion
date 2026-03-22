from __future__ import annotations

import unittest
from unittest.mock import patch

from core.monitor import SystemMonitor


def build_config() -> dict:
    return {
        "monitoring": {
            "cpu_alert_threshold": 85,
            "ram_alert_threshold": 90,
        }
    }


class SystemMonitorTests(unittest.TestCase):
    @patch("core.monitor.SystemMonitor.get_top_processes_by_cpu")
    @patch("core.monitor.psutil.virtual_memory")
    @patch("core.monitor.psutil.cpu_percent")
    def test_check_alerts_returns_threshold_breaches(
        self,
        mock_cpu,
        mock_virtual_memory,
        mock_top_processes,
    ) -> None:
        mock_cpu.return_value = 91.2
        mock_virtual_memory.return_value.percent = 93.4
        mock_top_processes.return_value = []

        monitor = SystemMonitor(build_config())
        alerts = monitor.check_alerts()

        self.assertEqual(len(alerts), 2)
        self.assertIn("CPU usage is 91.2%", alerts[0])
        self.assertIn("RAM usage is 93.4%", alerts[1])


if __name__ == "__main__":
    unittest.main()
