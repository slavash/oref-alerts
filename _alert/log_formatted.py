from __future__ import annotations

from datetime import datetime, timedelta


def write_formatted_entry(alert: dict, log_path: str) -> None:
    countdown = alert.get("original_countdown", 0)
    estimated = datetime.now() + timedelta(seconds=countdown)
    areas = ", ".join(alert.get("data", []))
    title = alert.get("title", "Alert")
    zone = alert.get("zone", "")
    alert_id = alert.get("id", "")

    entry = (
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
        f"ID: {alert_id} | "
        f"Title: {title} | "
        f"Zone: {zone} | "
        f"Areas: {areas} | "
        f"Estimated time: {estimated:%H:%M:%S}\n"
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
