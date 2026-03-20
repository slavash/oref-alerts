from __future__ import annotations

import os
import subprocess
import sys

from _alert.config import Config
from _alert.ipc import append_alert
from _alert.lock import try_acquire_lock


def send_to_popup(alert: dict, config: Config) -> None:
    append_alert(alert, config.alerts_ipc_path)

    if not try_acquire_lock(config.popup_lock_path):
        return

    python = config.venv_python_path if os.path.exists(config.venv_python_path) else sys.executable
    map_popup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "map_popup.py")
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "popup_stderr.log")
    with open(log_path, "a") as err_log:
        subprocess.Popen(
            [python, map_popup_path, "--popup"],
            stdout=subprocess.DEVNULL,
            stderr=err_log,
            start_new_session=True,
        )
