from __future__ import annotations

import json
from datetime import datetime


def write_raw_entry(alert: dict, log_path: str) -> None:
    entry = json.dumps(alert, ensure_ascii=False)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {entry}\n")
