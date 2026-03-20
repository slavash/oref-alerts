from __future__ import annotations

import json
from datetime import datetime
from urllib.request import urlopen, Request


def fetch_alert(url: str, headers: dict[str, str], timeout: int = 5) -> dict | None:
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8-sig").strip()
            if not body:
                return None
            return json.loads(body)
    except Exception as e:
        print(f"[{datetime.now():%H:%M:%S}] fetch error: {e}")
        return None
