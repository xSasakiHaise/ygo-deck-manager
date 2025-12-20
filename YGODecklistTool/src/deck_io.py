from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from deck_model import DeckEntry


def save_deck(path: str, header: Dict[str, str], entries: List[DeckEntry]) -> None:
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
            for entry in entries
        ],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_deck(path: str) -> Tuple[Dict[str, str], List[DeckEntry]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    header = {
        "player_name": payload.get("player_name", ""),
        "deck_name": payload.get("deck_name", ""),
        "event_name": payload.get("event_name", ""),
    }
    entries = []
    for entry in payload.get("entries", []):
        entries.append(
            DeckEntry(
                section=entry.get("section", "Main"),
                amount=int(entry.get("amount", 0)),
                name_eng=entry.get("name_eng", ""),
                name_ger=entry.get("name_ger", ""),
                card_id=entry.get("card_id", ""),
                set_code=entry.get("set_code", ""),
                rarity=entry.get("rarity", ""),
            )
        )
    return header, entries
