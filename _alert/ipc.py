from __future__ import annotations

import json
import os


def append_alert(alert: dict, ipc_path: str) -> None:
    alerts = read_alerts(ipc_path)
    alerts.append(alert)
    with open(ipc_path, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False)


def read_alerts(ipc_path: str) -> list[dict]:
    if not os.path.exists(ipc_path):
        return []
    try:
        with open(ipc_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
