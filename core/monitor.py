from __future__ import annotations

from typing import Any

import psutil


class SystemMonitor:
    def __init__(self, config: dict) -> None:
        monitoring_config = config["monitoring"]
        self.cpu_alert_threshold = float(monitoring_config["cpu_alert_threshold"])
        self.ram_alert_threshold = float(monitoring_config["ram_alert_threshold"])

    def get_cpu_percent(self) -> float:
        return float(psutil.cpu_percent(interval=None))

    def get_ram_percent(self) -> float:
        return float(psutil.virtual_memory().percent)

    def get_processes(self) -> list[dict[str, Any]]:
        processes: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info
                processes.append(
                    {
                        "pid": info.get("pid"),
                        "name": info.get("name") or "unknown",
                        "cpu_percent": float(info.get("cpu_percent") or 0.0),
                        "memory_percent": float(info.get("memory_percent") or 0.0),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes

    def get_top_processes_by_cpu(self, limit: int = 5) -> list[dict[str, Any]]:
        processes = self.get_processes()
        return sorted(processes, key=lambda item: item["cpu_percent"], reverse=True)[:limit]

    def get_status_snapshot(self) -> dict[str, Any]:
        return {
            "cpu_percent": self.get_cpu_percent(),
            "ram_percent": self.get_ram_percent(),
            "top_processes": self.get_top_processes_by_cpu(),
        }

    def check_alerts(self) -> list[str]:
        snapshot = self.get_status_snapshot()
        alerts: list[str] = []
        if snapshot["cpu_percent"] >= self.cpu_alert_threshold:
            alerts.append(
                f"CPU usage is {snapshot['cpu_percent']:.1f}% "
                f"(threshold {self.cpu_alert_threshold:.0f}%)"
            )
        if snapshot["ram_percent"] >= self.ram_alert_threshold:
            alerts.append(
                f"RAM usage is {snapshot['ram_percent']:.1f}% "
                f"(threshold {self.ram_alert_threshold:.0f}%)"
            )
        return alerts
