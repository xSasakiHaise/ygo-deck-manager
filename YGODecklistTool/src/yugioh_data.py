from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

PULL_RARITIES = {"Short Print", "Super Short Print"}


def _get_base_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[1]


def _load_json_asset(filename: str) -> Any:
    base = _get_base_path()
    path = base / "assets" / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing asset: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_cards() -> Dict[str, Dict[str, Any]]:
    data = _load_json_asset("cards.json")
    cards = data.get("data", [])
    by_name: Dict[str, Dict[str, Any]] = {}
    by_id: Dict[int, Dict[str, Any]] = {}
    for card in cards:
        name = card.get("name")
        card_id = card.get("id")
        if isinstance(name, str):
            by_name[name.lower()] = card
        if isinstance(card_id, int):
            by_id[card_id] = card
    return {"by_name": by_name, "by_id": by_id}


@lru_cache(maxsize=1)
def load_rarity_hierarchy_main() -> Dict[str, int]:
    return _load_json_asset("rarity_hierarchy_main.json")


@lru_cache(maxsize=1)
def load_rarity_hierarchy_extra_side() -> Dict[str, int]:
    return _load_json_asset("rarity_hierarchy_extra_side.json")


def search_card_names(prefix: str, limit: int = 20) -> List[str]:
    if not prefix:
        return []
    cards = load_cards()["by_name"]
    prefix_lower = prefix.lower()
    matches = [card["name"] for key, card in cards.items() if key.startswith(prefix_lower)]
    matches.sort()
    return matches[:limit]


def get_card_by_name(name: str) -> Optional[Dict[str, Any]]:
    if not name:
        return None
    return load_cards()["by_name"].get(name.lower())


def get_card_by_id(card_id: int) -> Optional[Dict[str, Any]]:
    return load_cards()["by_id"].get(card_id)


def _is_ocg_set_code(set_code: str) -> bool:
    code_upper = set_code.upper()
    if "-JP" in code_upper or code_upper.endswith("-JP"):
        return True
    if code_upper.startswith("JP"):
        return True
    if "JPP" in code_upper or "JPS" in code_upper:
        return True
    return False


def get_card_prints_tcg(card: Dict[str, Any]) -> List[Dict[str, Any]]:
    prints = card.get("card_sets", []) or []
    filtered = []
    for entry in prints:
        set_code = entry.get("set_code")
        rarity = entry.get("set_rarity")
        if not set_code or not rarity:
            continue
        if _is_ocg_set_code(set_code):
            continue
        if rarity in PULL_RARITIES:
            continue
        filtered.append(entry)
    return filtered


def extract_rarities_tcg(card: Dict[str, Any]) -> Set[str]:
    rarities = set()
    for entry in get_card_prints_tcg(card):
        rarity = entry.get("set_rarity")
        if rarity:
            rarities.add(rarity)
    return rarities


def is_extra_deck_monster(card: Optional[Dict[str, Any]]) -> bool:
    if not card:
        return False
    frame_type = str(card.get("frameType", "")).lower()
    if frame_type in {"fusion", "synchro", "xyz", "link"}:
        return True
    card_type = str(card.get("type", ""))
    return any(key in card_type.lower() for key in ["fusion", "synchro", "xyz", "link"])


def pick_example_set_codes_by_rarity(card: Dict[str, Any]) -> Dict[str, str]:
    examples: Dict[str, str] = {}
    for entry in get_card_prints_tcg(card):
        rarity = entry.get("set_rarity")
        set_code = entry.get("set_code")
        if not rarity or not set_code:
            continue
        current = examples.get(rarity)
        if current is None or set_code < current:
            examples[rarity] = set_code
    return examples
