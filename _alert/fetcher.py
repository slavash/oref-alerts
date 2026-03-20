"""OREF API client — fetches and parses alert JSON."""
from __future__ import annotations

import json
import ssl
from datetime import datetime
from urllib.request import urlopen, Request


def fetch_alert(url: str, headers: dict[str, str], timeout: int = 5) -> dict | None:
    """Fetch and parse a single alert from the OREF API."""
    # Create an SSL context that doesn't verify certificates (the OREF API
    # uses a self-signed certificate that fails default verification).
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8-sig").strip()
            if not body:
                return None
            return json.loads(body)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"[{datetime.now():%H:%M:%S}] fetch error: {e}")
        return None
