from __future__ import annotations

from datetime import date
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String

from deck_model import DeckEntry
from sort_utils import canonical_sort_entries
from yugioh_data import (
    PULL_RARITIES,
    extract_rarities_tcg,
    get_card_by_id,
    get_card_by_name,
    load_rarity_hierarchy_main,
    select_rarity_hierarchy,
)

OPTIONAL_MAX_DELTA = 5
RECOMMENDED_MIN_DELTA = 6


def _get_hierarchy(card: dict | None) -> Dict[str, int]:
    hierarchies = load_rarity_hierarchy_main()
    return select_rarity_hierarchy(hierarchies, card)


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


def _rarity_weight(hierarchy: Dict[str, int], rarity: str | None) -> int:
    return hierarchy.get(rarity or "", 0)


def _split_upgrade_rarities(
    rarities: list[str],
    hierarchy: Dict[str, int],
    current_weight: int,
) -> tuple[list[str], list[str]]:
    higher_rarities = [rarity for rarity in rarities if hierarchy.get(rarity, 0) > current_weight]
    if not higher_rarities:
        return [], []
    best_weight = max(hierarchy.get(rarity, 0) for rarity in higher_rarities)
    delta = best_weight - current_weight
    if delta >= RECOMMENDED_MIN_DELTA:
        recommended = [
            rarity
            for rarity in higher_rarities
            if hierarchy.get(rarity, 0) >= current_weight + RECOMMENDED_MIN_DELTA
        ]
        optional = [
            rarity
            for rarity in higher_rarities
            if current_weight < hierarchy.get(rarity, 0) <= current_weight + OPTIONAL_MAX_DELTA
        ]
        return recommended, optional
    return [], higher_rarities


def _build_certificate(
    player_name: str,
    deck_name: str,
    certificate_width: float,
) -> Drawing:
    certificate_height = 140 * mm
    outer_margin = 4 * mm
    inner_margin = 10 * mm
    title_y = certificate_height - 20 * mm
    line1_y = certificate_height - 40 * mm
    player_y = certificate_height - 55 * mm
    line2_y = certificate_height - 70 * mm
    deck_y = certificate_height - 85 * mm
    congrats_y = certificate_height - 105 * mm
    date_y = 12 * mm

    drawing = Drawing(certificate_width, certificate_height)
    drawing.add(
        Rect(
            0,
            0,
            certificate_width,
            certificate_height,
            strokeColor=colors.darkgoldenrod,
            fillColor=None,
            strokeWidth=1.2,
        )
    )
    drawing.add(
        Rect(
            outer_margin,
            outer_margin,
            certificate_width - 2 * outer_margin,
            certificate_height - 2 * outer_margin,
            strokeColor=colors.lightgoldenrodyellow,
            fillColor=None,
            strokeWidth=0.8,
        )
    )
    drawing.add(
        Rect(
            inner_margin,
            inner_margin,
            certificate_width - 2 * inner_margin,
            certificate_height - 2 * inner_margin,
            strokeColor=colors.grey,
            fillColor=None,
            strokeWidth=0.6,
        )
    )
    drawing.add(
        Line(
            inner_margin,
            certificate_height - 62 * mm,
            certificate_width - inner_margin,
            certificate_height - 62 * mm,
            strokeColor=colors.darkgoldenrod,
            strokeWidth=0.6,
        )
    )
    seal_radius = 12 * mm
    drawing.add(
        Circle(
            certificate_width - inner_margin - seal_radius,
            inner_margin + seal_radius + 6 * mm,
            seal_radius,
            strokeColor=colors.darkgoldenrod,
            fillColor=None,
            strokeWidth=1,
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            title_y,
            "Certificate of Max Rare Completion",
            fontName="Helvetica-Bold",
            fontSize=16,
            fillColor=colors.darkgoldenrod,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            line1_y,
            "This certifies that",
            fontName="Helvetica",
            fontSize=11,
            fillColor=colors.black,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            player_y,
            player_name,
            fontName="Helvetica-Bold",
            fontSize=14,
            fillColor=colors.black,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            line2_y,
            "has achieved Max Rare status for the deck",
            fontName="Helvetica",
            fontSize=11,
            fillColor=colors.black,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            deck_y,
            deck_name,
            fontName="Helvetica-Bold",
            fontSize=14,
            fillColor=colors.black,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            congrats_y,
            "Congratulations!",
            fontName="Helvetica-Bold",
            fontSize=12,
            fillColor=colors.darkgoldenrod,
            textAnchor="middle",
        )
    )
    drawing.add(
        String(
            certificate_width / 2,
            date_y,
            date.today().strftime("Generated on %Y-%m-%d"),
            fontName="Helvetica",
            fontSize=8,
            fillColor=colors.grey,
            textAnchor="middle",
        )
    )
    return drawing


def export_overview_pdf(path: str, header: Dict[str, str], entries: List[DeckEntry]) -> None:
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
    summary_style = ParagraphStyle(
        "overview-summary",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
    )

    story = [Paragraph("Print & Rarity Overview", title_style), Spacer(1, 6)]
    sorted_entries = canonical_sort_entries(entries)
    recommended_entries = 0
    optional_entries = 0

    for section in ["Main", "Extra", "Side"]:
        section_entries = [entry for entry in sorted_entries if entry.section == section]
        if not section_entries:
            continue
        story.append(Paragraph(f"{section} Deck", section_style))
        for entry in section_entries:
            card = _lookup_card(entry)
            hierarchy = _get_hierarchy(card)

            rarities = []
            if card is not None:
                rarities = [
                    rarity
                    for rarity in extract_rarities_tcg(card)
                    if _is_valid_rarity(rarity)
                ]
            rarities = sorted(rarities, key=lambda r: hierarchy.get(r, 0))

            current_weight = _rarity_weight(hierarchy, entry.rarity)
            best_weight = max((hierarchy.get(rarity, 0) for rarity in rarities), default=0)
            best_rarity = rarities[-1] if rarities else "—"
            delta = best_weight - current_weight
            recommended_rarities, optional_rarities = _split_upgrade_rarities(
                rarities,
                hierarchy,
                current_weight,
            )
            if recommended_rarities:
                recommended_entries += 1
            if optional_rarities:
                optional_entries += 1

            name_display = (
                f"{entry.name_ger} / {entry.name_eng}"
                if entry.name_ger
                else f"/ {entry.name_eng}"
            )
            title_line = f"{entry.amount}x {name_display} (ID: {entry.card_id})"
            story.append(Paragraph(title_line, title_line_style))
            current_details = " / ".join(
                part for part in [entry.set_code, entry.rarity] if part
            )
            current_line = (
                f"Current: {current_details} (W: {current_weight})"
                if current_details
                else f"Current: — (W: {current_weight})"
            )
            story.append(Paragraph(current_line, line_style))
            story.append(
                Paragraph(
                    f"Best available: {best_rarity} (W: {best_weight}, Δ={delta})",
                    line_style,
                )
            )

            if delta <= 0:
                story.append(Paragraph("Upgrades: —", line_style))
            else:
                if recommended_rarities:
                    story.append(
                        Paragraph(
                            f"Recommended upgrades: {', '.join(recommended_rarities)}",
                            line_style,
                        )
                    )
                if optional_rarities:
                    story.append(
                        Paragraph(
                            f"Optional upgrades: {', '.join(optional_rarities)}",
                            line_style,
                        )
                    )
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Summary", summary_style))
    story.append(
        Paragraph(
            f"Recommended upgrades remaining: {recommended_entries}",
            line_style,
        )
    )
    story.append(
        Paragraph(
            f"Optional upgrades remaining: {optional_entries}",
            line_style,
        )
    )

    if recommended_entries == 0:
        player_name = (header.get("player_name") or "").strip() or "(Unnamed Player)"
        deck_name = (header.get("deck_name") or "").strip() or "(Unnamed Deck)"
        story.append(PageBreak())
        story.append(_build_certificate(player_name, deck_name, doc.width))

    doc.build(story)
