"""Process lifecycle management for the popup subprocess."""
from __future__ import annotations

import os
import signal
import subprocess
import sys

from _alert.config import Config
from _alert.ipc import append_alert
from _alert.lock import try_acquire_lock, write_lock_pid

# Automatically reap child processes to prevent zombies.
signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def send_to_popup(alert: dict, config: Config) -> None:
    """Write *alert* to IPC and spawn the popup process if not already running."""
    append_alert(alert, config.alerts_ipc_path)

    if not try_acquire_lock(config.popup_lock_path):
        return

    python = (
        config.venv_python_path
        if os.path.exists(config.venv_python_path)
        else sys.executable
    )
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    map_popup_path = os.path.join(base_dir, "map_popup.py")
    log_path = os.path.join(base_dir, "popup_stderr.log")
    with open(log_path, "a", encoding="utf-8") as err_log:
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            [python, map_popup_path, "--popup"],
            stdout=subprocess.DEVNULL,
            stderr=err_log,
            start_new_session=True,
        )
    write_lock_pid(config.popup_lock_path, proc.pid)
