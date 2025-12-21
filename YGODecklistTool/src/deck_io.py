from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from deck_model import DeckEntry
from sort_utils import canonical_sort_entries


def save_deck(path: str, header: Dict[str, str], entries: List[DeckEntry]) -> None:
    sorted_entries = canonical_sort_entries(entries)
    payload = {
        "player_name": header.get("player_name", ""),
        "deck_name": header.get("deck_name", ""),
        "event_name": header.get("event_name", ""),
        "entries": [
            {
                "section": entry.section,
                "amount": entry.amount,
                "name_eng": entry.name_eng,
                "name_ger": entry.name_ger,
                "card_id": entry.card_id,
                "set_code": entry.set_code,
                "rarity": entry.rarity,
            }
            for entry in sorted_entries
        ],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_deck(path: str) -> Tuple[Dict[str, str], List[DeckEntry]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        entries_payload = payload
    else:
        entries_payload = payload.get("entries", []) if isinstance(payload, dict) else []

    header = {
        "player_name": payload.get("player_name", "") if isinstance(payload, dict) else "",
        "deck_name": payload.get("deck_name", "") if isinstance(payload, dict) else "",
        "event_name": payload.get("event_name", "") if isinstance(payload, dict) else "",
    }

    def normalize_entry(raw: dict) -> DeckEntry:
        def pick_value(keys: List[str]) -> str:
            for key in keys:
                if key in raw and raw.get(key) is not None:
                    return str(raw.get(key))
            return ""

        section = pick_value(["section"]).strip() or "Main"
        if section not in {"Main", "Extra", "Side"}:
            section = "Main"

        amount_raw = pick_value(["amount", "qty", "quantity"]).strip()
        try:
            amount = int(amount_raw)
        except ValueError:
            amount = 1
        if amount < 1:
            amount = 1

        name_eng = pick_value(["name_eng", "name"]).strip()
        name_ger = pick_value(["name_ger", "name_de"]).strip()
        card_id = pick_value(["card_id", "cardid", "id"]).strip()
        set_code = pick_value(["set_code", "set_id", "set"]).strip()
        rarity = pick_value(["rarity", "rarity_name"]).strip()

        return DeckEntry(
            section=section,
            amount=amount,
            name_eng=name_eng,
            name_ger=name_ger,
            card_id=card_id,
            set_code=set_code,
            rarity=rarity,
        )

    entries = []
    for entry in entries_payload:
        if not isinstance(entry, dict):
            continue
        entries.append(normalize_entry(entry))

    return header, canonical_sort_entries(entries)
