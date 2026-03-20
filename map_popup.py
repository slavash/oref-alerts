"""Show alert locations on a floating map popup using a native macOS WebKit window.

Design:
- A shared JSON file (/tmp/oref_alerts.json) acts as the IPC channel.
- An atomic lock file prevents multiple popup processes from launching.
- The popup process polls the IPC file every second, picks up new alerts,
  updates the webview, and resets its 60-second auto-close timer.

Usage from alert.py:  send_to_popup(alert_dict)
Also runnable standalone: python3 map_popup.py '{"title":"...", "data":[...]}'
"""
from __future__ import annotations

import json
import sys

from _alert.config import default_config
from _alert.ipc import append_alert as _append_alert_impl
from _alert.cities import load_cities
from _alert.html_builder import build_html
from _alert.popup_launcher import send_to_popup as _send_to_popup_impl

_config = default_config()

ALERTS_IPC = _config.alerts_ipc_path
POPUP_LOCK_FILE = _config.popup_lock_path
MY_LOCATION = _config.my_location
AUTO_CLOSE_SECONDS = _config.auto_close_seconds
MAP_TEMPLATE = _config.map_template_path
CITIES_JSON = _config.cities_json_path
VENV_PYTHON = _config.venv_python_path

_cities_db: list[dict] | None = None


def _get_cities_db() -> list[dict]:
    global _cities_db
    if _cities_db is None:
        _cities_db = load_cities(CITIES_JSON)
    return _cities_db


def _build_html(alerts: list[dict]) -> str:
    cities_db = _get_cities_db()
    return build_html(alerts, cities_db, MAP_TEMPLATE)


def _append_alert(alert: dict) -> None:
    _append_alert_impl(alert, ALERTS_IPC)


def send_to_popup(alert: dict) -> None:
    _send_to_popup_impl(alert, _config)


def _run_popup() -> None:
    from _alert.popup import run_popup
    run_popup(_config)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--popup":
        _run_popup()
    elif len(sys.argv) >= 2:
        alert = json.loads(sys.argv[1])
        _append_alert(alert)
        _run_popup()
    else:
        print("Usage: python3 map_popup.py --popup | '<alert_json>'")
        sys.exit(1)
