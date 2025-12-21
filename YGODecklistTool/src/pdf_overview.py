from __future__ import annotations

from typing import Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from deck_model import DeckEntry
from sort_utils import canonical_sort_entries
from yugioh_data import (
    PULL_RARITIES,
    extract_rarities_tcg,
    get_card_by_id,
    get_card_by_name,
    is_extra_deck_monster,
    load_rarity_hierarchy_extra_side,
    load_rarity_hierarchy_main,
)


def _get_hierarchy(section: str, card: dict | None) -> Dict[str, int]:
    if section == "Extra":
        return load_rarity_hierarchy_extra_side()
    if section == "Side" and card is not None and is_extra_deck_monster(card):
        return load_rarity_hierarchy_extra_side()
    return load_rarity_hierarchy_main()


def _is_valid_rarity(value: str) -> bool:
    if not value:
        return False
    if value.strip().isdigit():
        return False
    if value.strip().lower() == "new":
        return False
    if value in PULL_RARITIES:
        return False
    return True


def _lookup_card(entry: DeckEntry) -> dict | None:
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


def export_overview_pdf(path: str, entries: List[DeckEntry]) -> None:
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "overview-title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "overview-section",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceBefore=10,
        spaceAfter=6,
    )
    line_style = ParagraphStyle(
        "overview-line",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        spaceAfter=2,
    )
    title_line_style = ParagraphStyle(
        "overview-title-line",
        parent=line_style,
        fontName="Helvetica-Bold",
    )

    story = [Paragraph("Print & Rarity Overview", title_style), Spacer(1, 6)]
    sorted_entries = canonical_sort_entries(entries)

    for section in ["Main", "Extra", "Side"]:
        section_entries = [entry for entry in sorted_entries if entry.section == section]
        if not section_entries:
            continue
        story.append(Paragraph(f"{section} Deck", section_style))
        for entry in section_entries:
            card = _lookup_card(entry)
            hierarchy = _get_hierarchy(entry.section, card)

            rarities = []
            if card is not None:
                rarities = [
                    rarity
                    for rarity in extract_rarities_tcg(card)
                    if _is_valid_rarity(rarity)
                ]
            rarities = sorted(rarities, key=lambda r: hierarchy.get(r, 0))

            current_rank = hierarchy.get(entry.rarity, 0)
            upgrade_rarities = [r for r in rarities if hierarchy.get(r, 0) > current_rank]
            best_rarity = rarities[-1] if rarities else "—"

            name_display = (
                f"{entry.name_ger} / {entry.name_eng}" if entry.name_ger else entry.name_eng
            )
            title_line = f"{entry.amount}x {name_display} (ID: {entry.card_id})"
            story.append(Paragraph(title_line, title_line_style))
            current_line = (
                f"Current: {entry.set_code} / {entry.rarity}".strip()
                if entry.set_code or entry.rarity
                else "Current: —"
            )
            story.append(Paragraph(current_line, line_style))
            story.append(Paragraph(f"Best available: {best_rarity}", line_style))

            if upgrade_rarities:
                story.append(Paragraph(f\"Upgrades: {', '.join(upgrade_rarities)}\", line_style))
            else:
                story.append(Paragraph("Upgrades: —", line_style))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 10))

    doc.build(story)
