#!/usr/bin/env python3
"""Polls the OREF alert API and shows a macOS alert dialog + map on new messages."""
from __future__ import annotations

import os
import time
from datetime import datetime

from _alert.config import default_config
from _alert.dedup import AlertDeduplicator
from _alert.fetcher import fetch_alert as _fetch_alert
from _alert.log_formatted import write_formatted_entry
from _alert.log_raw import write_raw_entry
from _alert.beep import beep_if_local as _beep_if_local
from map_popup import send_to_popup, MY_LOCATION

_config = default_config()

URL = _config.api_url
POLL_INTERVAL = _config.poll_interval
HEADERS = dict(_config.http_headers)
FORMATTED_LOG = _config.formatted_log_path
RAW_LOG = _config.raw_log_path

_dedup = AlertDeduplicator()
seen_ids = _dedup.seen_ids


def fetch_alert() -> dict | None:
    return _fetch_alert(URL, HEADERS)


def log_formatted(alert: dict) -> None:
    write_formatted_entry(alert, FORMATTED_LOG)


def log_raw(alert: dict) -> None:
    write_raw_entry(alert, RAW_LOG)


def beep_if_local(alert: dict) -> None:
    _beep_if_local(alert, MY_LOCATION)


def ensure_log_files() -> None:
    for path in (FORMATTED_LOG, RAW_LOG):
        if not os.path.exists(path):
            open(path, "w", encoding="utf-8").close()


def main() -> None:
    ensure_log_files()
    print(f"Polling {URL} every {POLL_INTERVAL}s …")
    print(f"Formatted log: {FORMATTED_LOG}")
    print(f"Raw log:       {RAW_LOG}")
    while True:
        alert = fetch_alert()
        if alert and alert.get("id") and alert["id"] not in seen_ids:
            seen_ids.add(alert["id"])
            print(f"[{datetime.now():%H:%M:%S}] new alert: {alert['id']}")
            log_raw(alert)
            beep_if_local(alert)
            send_to_popup(alert)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
