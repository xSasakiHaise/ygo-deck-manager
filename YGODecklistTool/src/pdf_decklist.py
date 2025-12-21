from __future__ import annotations

from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from deck_model import DeckEntry
from sort_utils import canonical_sort_entries


def export_decklist_pdf(path: str, header: Dict[str, str], entries: List[DeckEntry]) -> None:
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
        "decklist-title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        spaceAfter=6,
    )
    header_style = ParagraphStyle(
        "decklist-header",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "decklist-section",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        spaceBefore=8,
        spaceAfter=4,
    )
    table_header_style = ParagraphStyle(
        "decklist-table-header",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
    )
    table_body_style = ParagraphStyle(
        "decklist-table-body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
    )

    story = [
        Paragraph("Yu-Gi-Oh! TCG Deck List", title_style),
        Paragraph(f"Player: {header.get('player_name', '')}", header_style),
        Paragraph(f"Deck Name: {header.get('deck_name', '')}", header_style),
        Paragraph(f"Event: {header.get('event_name', '')}", header_style),
        Spacer(1, 6),
    ]

    counts = {"Main": 0, "Extra": 0, "Side": 0}
    for entry in entries:
        counts[entry.section] = counts.get(entry.section, 0) + entry.amount

    sorted_entries = canonical_sort_entries(entries)
    column_widths = [28, 150, 150, 58, 50, 90]
    headers = ["Qty", "Name (GER)", "Name (ENG)", "Card ID", "Set ID", "Rarity"]

    for section in ["Main", "Extra", "Side"]:
        section_entries = [entry for entry in sorted_entries if entry.section == section]
        if not section_entries:
            continue
        story.append(Paragraph(f"{section} Deck ({counts.get(section, 0)} cards)", section_style))
        table_data = [
            [Paragraph(text, table_header_style) for text in headers],
        ]
        for entry in section_entries:
            table_data.append(
                [
                    Paragraph(str(entry.amount), table_body_style),
                    Paragraph(entry.name_ger or "", table_body_style),
                    Paragraph(entry.name_eng or "", table_body_style),
                    Paragraph(entry.card_id or "", table_body_style),
                    Paragraph(entry.set_code or "", table_body_style),
                    Paragraph(entry.rarity or "", table_body_style),
                ]
            )
        table = Table(table_data, colWidths=column_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 8))

    doc.build(story)
