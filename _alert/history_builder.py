"""Rebuild history.html by injecting current data into the template."""
from __future__ import annotations

import json


def _replace_marker(html: str, begin: str, end: str, data_str: str) -> str:
    """Replace content between *begin* and *end* markers with *data_str*."""
    start = html.index(begin) + len(begin)
    stop = html.index(end, start)
    return html[:start] + data_str + html[stop:]


def rebuild_history_html(
    history_html_path: str,
    alerts_history_path: str,
    cities_json_path: str,
) -> None:
    """Replace the CITIES_JSON and ALERTS_JSON placeholders in *history_html_path*."""
    with open(history_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    with open(cities_json_path, "r", encoding="utf-8") as f:
        cities = json.load(f)

    with open(alerts_history_path, "r", encoding="utf-8") as f:
        alerts = json.load(f)

    cities_str = json.dumps(cities, ensure_ascii=False)
    alerts_str = json.dumps(alerts, ensure_ascii=False)

    html = _replace_marker(html, "/*CITIES_JSON*/", "/*END_CITIES_JSON*/", cities_str)
    html = _replace_marker(html, "/*ALERTS_JSON*/", "/*END_ALERTS_JSON*/", alerts_str)

    with open(history_html_path, "w", encoding="utf-8") as f:
        f.write(html)
