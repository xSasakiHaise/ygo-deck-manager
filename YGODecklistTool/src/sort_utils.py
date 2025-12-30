from __future__ import annotations

from typing import Optional

from deck_model import DeckEntry
from yugioh_data import (
    get_card_by_id,
    get_card_by_name,
    load_rarity_hierarchy_main,
    select_rarity_hierarchy,
)

SECTION_ORDER = {"Main": 0, "Extra": 1, "Side": 2}


def section_rank(section: str) -> int:
    return SECTION_ORDER.get(section, 99)


def _safe_casefold(value: str) -> str:
    return value.casefold() if value else ""


def _lookup_card(entry: DeckEntry) -> Optional[dict]:
    card = None
    if entry.card_id:
        try:
            card = get_card_by_id(int(entry.card_id))
        except (ValueError, FileNotFoundError):
            card = None
    if card is None and entry.name_eng:
        try:
            card = get_card_by_name(entry.name_eng)
        except FileNotFoundError:
            card = None
    return card


def rarity_rank_for_entry(entry: DeckEntry, card_dict: Optional[dict]) -> int:
    hierarchies = load_rarity_hierarchy_main()
    hierarchy = select_rarity_hierarchy(hierarchies, card_dict)
    return hierarchy.get(entry.rarity or "", 0)


def canonical_sort_key(entry: DeckEntry) -> tuple:
    card_dict = _lookup_card(entry)
    name_ger = entry.name_ger or ""
    name_eng = entry.name_eng or ""
    primary_name = name_ger or name_eng
    set_code = entry.set_code or ""
    rarity = entry.rarity or ""
    return (
        section_rank(entry.section),
        _safe_casefold(primary_name),
        _safe_casefold(name_eng),
        _safe_casefold(set_code),
        rarity_rank_for_entry(entry, card_dict),
        _safe_casefold(rarity),
        entry.amount,
    )


def canonical_sort_entries(entries: list[DeckEntry]) -> list[DeckEntry]:
    return sorted(entries, key=canonical_sort_key)
