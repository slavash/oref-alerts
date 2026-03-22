"""Raw JSON-per-line log persistence."""
from __future__ import annotations

import json
from datetime import datetime


def write_raw_entry(alert: dict, log_path: str) -> None:
    """Append a timestamped JSON entry for *alert* to *log_path*."""
    entry = json.dumps(alert, ensure_ascii=False)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {entry}\n")


def append_history_json(alert: dict, history_path: str) -> None:
    """Append *alert* (with timestamp) to the history JSON array file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {**alert, "ts": ts}

    try:
        with open(history_path, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (OSError, json.JSONDecodeError):
        history = []

    history.insert(0, record)

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)
