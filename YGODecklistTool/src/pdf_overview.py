from __future__ import annotations

from typing import Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from deck_model import DeckEntry
from yugioh_data import (
    extract_rarities_tcg,
    get_card_by_id,
    get_card_by_name,
    is_extra_deck_monster,
    load_rarity_hierarchy_extra_side,
    load_rarity_hierarchy_main,
    pick_example_set_codes_by_rarity,
)


def _get_hierarchy(section: str, card: dict | None) -> Dict[str, int]:
    if section == "Extra":
        return load_rarity_hierarchy_extra_side()
    if section == "Side" and card is not None:
        if is_extra_deck_monster(card):
            return load_rarity_hierarchy_extra_side()
    return load_rarity_hierarchy_main()


def export_overview_pdf(path: str, entries: List[DeckEntry]) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def draw_page_header() -> float:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, height - 20 * mm, "Print & Rarity Overview")
        return height - 28 * mm

    def draw_section_header(title: str, y: float) -> float:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y, title)
        return y - 6 * mm

    def draw_text_line(text: str, y: float, indent: float = 0) -> float:
        c.setFont("Helvetica", 9)
        c.drawString((20 + indent) * mm, y, text)
        return y - 5 * mm

    y = draw_page_header()
    for section in ["Main", "Extra", "Side"]:
        section_entries = [entry for entry in entries if entry.section == section]
        if not section_entries:
            continue
        y = draw_section_header(f"{section} Deck", y)
        for entry in section_entries:
            if y < 25 * mm:
                c.showPage()
                y = draw_page_header()
                y = draw_section_header(f"{section} Deck (cont.)", y)

            card = None
            if entry.card_id:
                try:
                    card = get_card_by_id(int(entry.card_id))
                except ValueError:
                    card = None
            if card is None and entry.name_eng:
                card = get_card_by_name(entry.name_eng)

            hierarchy = _get_hierarchy(entry.section, card)
            rarities = []
            example_codes: Dict[str, str] = {}
            if card is not None:
                rarities = sorted(
                    extract_rarities_tcg(card),
                    key=lambda r: hierarchy.get(r, 0),
                )
                example_codes = pick_example_set_codes_by_rarity(card)

            current_rank = hierarchy.get(entry.rarity, 0)
            upgrade_rarities = [r for r in rarities if hierarchy.get(r, 0) > current_rank]
            best_rarity = rarities[-1] if rarities else ""

            name_display = f"{entry.name_ger} / {entry.name_eng}".strip(" /")
            y = draw_text_line(f"{entry.amount}x {name_display} (ID: {entry.card_id})", y)
            current_text = f"Current: {entry.set_code} / {entry.rarity}".strip()
            y = draw_text_line(current_text, y, indent=4)
            y = draw_text_line(f"Best available: {best_rarity}", y, indent=4)

            if rarities:
                available_parts = []
                for rarity in rarities:
                    code = example_codes.get(rarity, "")
                    suffix = f" ({code})" if code else ""
                    available_parts.append(f"{rarity}{suffix}")
                y = draw_text_line(f"Available rarities: {', '.join(available_parts)}", y, indent=4)

            if upgrade_rarities:
                upgrade_parts = []
                for rarity in upgrade_rarities:
                    code = example_codes.get(rarity, "")
                    suffix = f" ({code})" if code else ""
                    upgrade_parts.append(f"{rarity}{suffix}")
                y = draw_text_line(f"Upgrades: {', '.join(upgrade_parts)}", y, indent=4)
            else:
                y = draw_text_line("Upgrades: None", y, indent=4)

            y -= 2 * mm

        y -= 4 * mm

    c.showPage()
    c.save()
