"""
Gear database loader.

Data lives in gear_db.json alongside this file so it can be edited by the
Dev Tools page without touching Python source.
"""

import json
from pathlib import Path

_JSON_PATH = Path(__file__).parent / "gear_db.json"


def load() -> dict[str, dict[str, dict]]:
    with open(_JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save(db: dict[str, dict[str, dict]]) -> None:
    with open(_JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(db, fh, indent=2, ensure_ascii=False)
    # Bust the cached reference so callers re-import fresh data.
    global GEAR_DB
    GEAR_DB = db


GEAR_DB: dict[str, dict[str, dict]] = load()