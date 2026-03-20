from __future__ import annotations

import subprocess


def beep_if_local(alert: dict, my_location: str) -> None:
    areas = alert.get("data", [])
    if my_location in areas:
        subprocess.Popen(["osascript", "-e", "beep"])
