from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RARITY_MULTIPLIERS: dict[str, float] = {
    "Common": 1.0,
    "Rare": 1.0,
    "Super Rare": 1.2,
    "Ultra Rare": 1.6,
    "Secret Rare": 2.1,
    "Prismatic Secret Rare": 2.4,
    "Ghost Rare": 5.5,
    "Ultimate Rare": 4.5,
    "Collector's Rare": 3.6,
    "Starlight Rare": 4.0,
    "Quarter Century Secret Rare": 5.0,
    "Starfoil Rare": 1.3,
    "Shatterfoil Rare": 1.3,
    "Mosaic Rare": 1.3,
    "Super Parallel Rare": 1.4,
    "Ultra Parallel Rare": 1.8,
    "Secret Parallel Rare": 2.3,
    "Blue Ultra Rare": 1.6,
    "Green Ultra Rare": 1.6,
    "Red Ultra Rare": 1.6,
    "Gold Rare": 2.2,
    "Premium Gold Rare": 2.4,
    "Gold Secret Rare": 3.2,
    "Platinum Rare": 2.0,
    "Platinum Secret Rare": 2.6,
}


def _base_price_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "base_prices.json"


@lru_cache(maxsize=1)
def _load_base_prices() -> dict[str, float]:
    path = _base_price_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned: dict[str, float] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        try:
            cleaned[key] = float(value)
        except (TypeError, ValueError):
            continue
    return cleaned


def get_base_price(card_name: str) -> float:
    if not card_name:
        return 0.0
    return _load_base_prices().get(card_name, 0.0)


def get_rarity_multiplier(rarity_name: str) -> float:
    if not rarity_name:
        return 1.0
    return RARITY_MULTIPLIERS.get(rarity_name, 1.0)
