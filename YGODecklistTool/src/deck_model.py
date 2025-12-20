from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DeckEntry:
    section: str
    amount: int
    name_eng: str
    name_ger: str = ""
    card_id: str = ""
    set_code: str = ""
    rarity: str = ""


class DeckModel:
    def __init__(self) -> None:
        self.entries: List[DeckEntry] = []

    def add_entry(self, entry: DeckEntry) -> None:
        self.entries.append(entry)

    def update_entry(self, index: int, entry: DeckEntry) -> None:
        self.entries[index] = entry

    def delete_entry(self, index: int) -> None:
        del self.entries[index]

    def get_entry(self, index: int) -> Optional[DeckEntry]:
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None

    def counts(self) -> dict:
        counts = {"Main": 0, "Extra": 0, "Side": 0}
        for entry in self.entries:
            if entry.section in counts:
                counts[entry.section] += entry.amount
        return counts
