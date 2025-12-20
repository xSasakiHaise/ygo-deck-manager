from __future__ import annotations

from typing import Dict, List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from deck_model import DeckEntry


def export_decklist_pdf(path: str, header: Dict[str, str], entries: List[DeckEntry]) -> None:
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def draw_page_header() -> float:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, height - 20 * mm, "Yu-Gi-Oh! TCG Deck List")
        c.setFont("Helvetica", 10)
        c.drawString(20 * mm, height - 28 * mm, f"Player: {header.get('player_name', '')}")
        c.drawString(20 * mm, height - 34 * mm, f"Deck Name: {header.get('deck_name', '')}")
        c.drawString(20 * mm, height - 40 * mm, f"Event: {header.get('event_name', '')}")
        return height - 48 * mm

    def draw_table_header(y: float) -> float:
        c.setFont("Helvetica-Bold", 9)
        headers = ["Qty", "Name (GER)", "Name (ENG)", "Card ID", "Set ID", "Rarity"]
        x_positions = [20, 35, 90, 145, 175, 200]
        for header_text, x in zip(headers, x_positions):
            c.drawString(x * mm, y, header_text)
        c.line(20 * mm, y - 2, width - 20 * mm, y - 2)
        return y - 8

    def draw_row(entry: DeckEntry, y: float) -> float:
        c.setFont("Helvetica", 9)
        values = [
            str(entry.amount),
            entry.name_ger,
            entry.name_eng,
            entry.card_id,
            entry.set_code,
            entry.rarity,
        ]
        x_positions = [20, 35, 90, 145, 175, 200]
        for value, x in zip(values, x_positions):
            c.drawString(x * mm, y, value)
        return y - 7 * mm

    counts = {"Main": 0, "Extra": 0, "Side": 0}
    for entry in entries:
        counts[entry.section] = counts.get(entry.section, 0) + entry.amount

    sections = ["Main", "Extra", "Side"]
    y = draw_page_header()
    y = draw_table_header(y)

    for section in sections:
        section_entries = [entry for entry in entries if entry.section == section]
        if not section_entries:
            continue
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, f"{section} Deck ({counts.get(section, 0)})")
        y -= 6 * mm
        y = draw_table_header(y)
        for entry in section_entries:
            if y < 25 * mm:
                c.showPage()
                y = draw_page_header()
                y = draw_table_header(y)
            y = draw_row(entry, y)
        y -= 4 * mm

    c.showPage()
    c.save()
