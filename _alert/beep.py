"""Audio notification via osascript when local city is in alert data."""
from __future__ import annotations

import subprocess


def beep_if_local(alert: dict, my_location: str) -> None:
    """Play an audible beep if *my_location* appears in the alert areas."""
    areas = alert.get("data", [])
    if my_location in areas:
        subprocess.Popen(["osascript", "-e", "beep"])  # pylint: disable=consider-using-with
