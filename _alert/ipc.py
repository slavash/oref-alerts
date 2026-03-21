"""Inter-process communication via a shared JSON file."""
from __future__ import annotations

import json
import os


def write_alerts(alerts: list[dict], ipc_path: str) -> None:
    """Replace the IPC file with *alerts*."""
    with open(ipc_path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False)


def append_alert(alert: dict, ipc_path: str) -> None:
    """Append *alert* to the IPC JSON file at *ipc_path*."""
    alerts = read_alerts(ipc_path)
    alerts.append(alert)
    write_alerts(alerts, ipc_path)


def read_alerts(ipc_path: str) -> list[dict]:
    """Read all alerts from the IPC JSON file."""
    if not os.path.exists(ipc_path):
        return []
    try:
        with open(ipc_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
