from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

PULL_RARITIES = {"Short Print", "Super Short Print"}

RARITY_HIERARCHY_DEFAULT = "effect_monster"
FRAME_TYPE_TO_HIERARCHY_KEY = {
    "normal": "normal_monster",
    "effect": "effect_monster",
    "spell": "spell",
    "trap": "trap",
    "fusion": "fusion",
    "synchro": "synchro",
    "xyz": "xyz",
    "link": "link",
    "ritual": "ritual",
    "token": "token",
    "pendulum_normal": "pendulum_normal",
    "normal_pendulum": "pendulum_normal",
    "pendulum_effect": "pendulum_effect",
    "effect_pendulum": "pendulum_effect",
    "pendulum_ritual": "pendulum_ritual",
    "ritual_pendulum": "pendulum_ritual",
    "pendulum_fusion": "pendulum_fusion",
    "fusion_pendulum": "pendulum_fusion",
    "pendulum_synchro": "pendulum_synchro",
    "synchro_pendulum": "pendulum_synchro",
    "pendulum_xyz": "pendulum_xyz",
    "xyz_pendulum": "pendulum_xyz",
}


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


LANGUAGE_ASSETS = {
    "en": "cards.json",
    "de": "cards_de.json",
}


@lru_cache(maxsize=4)
def load_cards(language: str = "en") -> Dict[str, Dict[str, Any]]:
    filename = LANGUAGE_ASSETS.get(language, LANGUAGE_ASSETS["en"])
    data = _load_json_asset(filename)
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
def load_rarity_hierarchy_main() -> Dict[str, Dict[str, int]]:
    return _load_json_asset("rarity_hierarchy_main.json")


def _pendulum_key_from_type(type_label: str) -> Optional[str]:
    if "pendulum" not in type_label:
        return None
    if "normal" in type_label:
        return "pendulum_normal"
    if "ritual" in type_label:
        return "pendulum_ritual"
    if "fusion" in type_label:
        return "pendulum_fusion"
    if "synchro" in type_label:
        return "pendulum_synchro"
    if "xyz" in type_label:
        return "pendulum_xyz"
    if "effect" in type_label:
        return "pendulum_effect"
    return "pendulum_effect"


def _key_from_type_label(type_label: str) -> Optional[str]:
    pendulum_key = _pendulum_key_from_type(type_label)
    if pendulum_key:
        return pendulum_key
    if "spell" in type_label:
        return "spell"
    if "trap" in type_label:
        return "trap"
    if "token" in type_label:
        return "token"
    if "ritual" in type_label:
        return "ritual"
    if "fusion" in type_label:
        return "fusion"
    if "synchro" in type_label:
        return "synchro"
    if "xyz" in type_label:
        return "xyz"
    if "link" in type_label:
        return "link"
    if "normal" in type_label:
        return "normal_monster"
    if "effect" in type_label:
        return "effect_monster"
    return None


def rarity_hierarchy_key_for_card(card: Optional[Dict[str, Any]]) -> str:
    if not card:
        return RARITY_HIERARCHY_DEFAULT
    frame_type = str(card.get("frameType", "")).lower()
    if frame_type:
        key = FRAME_TYPE_TO_HIERARCHY_KEY.get(frame_type)
        if key:
            return key
    type_label = str(card.get("type", "")).lower()
    key = _key_from_type_label(type_label)
    if key:
        return key
    return RARITY_HIERARCHY_DEFAULT


def select_rarity_hierarchy(
    hierarchies: Dict[str, Dict[str, int]],
    card: Optional[Dict[str, Any]],
) -> Dict[str, int]:
    key = rarity_hierarchy_key_for_card(card)
    if key in hierarchies:
        return hierarchies[key]
    if RARITY_HIERARCHY_DEFAULT in hierarchies:
        return hierarchies[RARITY_HIERARCHY_DEFAULT]
    return next(iter(hierarchies.values()), {})


def search_card_names(prefix: str, limit: int = 20, language: str = "en") -> List[str]:
    if not prefix:
        return []
    cards = load_cards(language)["by_name"]
    prefix_lower = prefix.lower()
    matches = [card["name"] for key, card in cards.items() if key.startswith(prefix_lower)]
    matches.sort()
    return matches[:limit]


def get_card_by_name(name: str, language: str = "en") -> Optional[Dict[str, Any]]:
    if not name:
        return None
    return load_cards(language)["by_name"].get(name.lower())


def get_card_by_id(card_id: int, language: str = "en") -> Optional[Dict[str, Any]]:
    return load_cards(language)["by_id"].get(card_id)


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
