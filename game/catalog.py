from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent / "data"


@lru_cache(maxsize=None)
def load_buildings() -> dict[str, dict[str, Any]]:
    with (DATA_DIR / "buildings.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def load_civilizations() -> list[dict[str, Any]]:
    with (DATA_DIR / "civilizations.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def load_tips() -> dict[str, dict[str, Any]]:
    with (DATA_DIR / "tips.json").open(encoding="utf-8") as fh:
        return {tip["id"]: tip for tip in json.load(fh)}


BUILDINGS = load_buildings()

CATEGORIES: list[dict[str, str]] = [
    {"id": "power", "label": "Power"},
    {"id": "housing", "label": "Housing"},
    {"id": "commerce", "label": "Commerce"},
    {"id": "industry", "label": "Industry"},
    {"id": "green", "label": "Green"},
    {"id": "infrastructure", "label": "Infrastructure"},
    {"id": "war", "label": "Defence"},
]


def building_stats(building_type: str) -> dict[str, Any]:
    return BUILDINGS[building_type]
