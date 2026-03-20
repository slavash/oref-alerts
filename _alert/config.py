from __future__ import annotations

import os
from dataclasses import dataclass, field

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    return int(raw) if raw is not None else default


@dataclass
class Config:
    api_url: str = field(default_factory=lambda: _env(
        "OREF_API_URL", "https://www.oref.org.il/WarningMessages/Alert/alerts.json"))
    poll_interval: int = field(default_factory=lambda: _env_int("OREF_POLL_INTERVAL", 2))
    http_headers: dict[str, str] = field(default_factory=lambda: {
        "Referer": "https://www.oref.org.il/",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
    })
    formatted_log_path: str = field(
        default_factory=lambda: _env("OREF_FORMATTED_LOG", os.path.join(_DIR, "alerts_formatted.txt")))
    raw_log_path: str = field(
        default_factory=lambda: _env("OREF_RAW_LOG", os.path.join(_DIR, "alerts_raw.txt")))
    my_location: str = field(default_factory=lambda: _env("OREF_MY_LOCATION", "חיפה"))
    auto_close_seconds: int = field(default_factory=lambda: _env_int("OREF_AUTO_CLOSE_SECONDS", 60))
    alerts_ipc_path: str = field(
        default_factory=lambda: _env("OREF_ALERTS_IPC", "/tmp/oref_alerts.json"))
    popup_lock_path: str = field(
        default_factory=lambda: _env("OREF_POPUP_LOCK", "/tmp/oref_popup.lock"))
    cities_json_path: str = field(
        default_factory=lambda: _env("OREF_CITIES_JSON", os.path.join(_DIR, "cities.json")))
    map_template_path: str = field(
        default_factory=lambda: _env("OREF_MAP_TEMPLATE", os.path.join(_DIR, "map.html")))
    venv_python_path: str = field(
        default_factory=lambda: _env("OREF_VENV_PYTHON", os.path.join(_DIR, ".venv", "bin", "python3")))


def default_config() -> Config:
    return Config()
