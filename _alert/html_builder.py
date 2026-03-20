from __future__ import annotations

import json


def build_html(alerts: list[dict], cities_db: list[dict], template_path: str) -> str:
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    alerts_json = json.dumps(alerts, ensure_ascii=False)
    cities_json = json.dumps(cities_db, ensure_ascii=False)

    return template.replace(
        "/*ALERTS_JSON*/null/*END_ALERTS_JSON*/", alerts_json
    ).replace(
        "/*CITIES_JSON*/[]/*END_CITIES_JSON*/", cities_json
    )
