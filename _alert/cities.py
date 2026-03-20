"""City location database loader."""
from __future__ import annotations

import json
import os


def load_cities(path: str) -> list[dict]:
    """Load the cities JSON database from *path*."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
