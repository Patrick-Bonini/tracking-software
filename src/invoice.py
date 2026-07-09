from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .db import fetch_billable_time_entries, fetch_project, fetch_settings, mark_time_entries_invoiced


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INVOICE_DIR = DATA_DIR / "invoices"


@dataclass(frozen=True)
class InvoiceLineItem:
    task_name: str
    raw_seconds: int
    rounded_hours: Decimal
    amount: Decimal


def _round_seconds_to_quarter_hours(seconds: int) -> Decimal:
    quarter_hours = Decimal(ceil(max(seconds, 0) / 900)) / Decimal(4)
    return quarter_hours.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)


def _format_money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _format_hours(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP):.2f}"


def _group_invoice_items(project_id: int, start_date: str, end_date: str) -> tuple[list[InvoiceLineItem], list[int]]:
    rows = fetch_billable_time_entries(project_id, start_date, end_date)
    if not rows:
        return [], []

    grouped_seconds: dict[str, int] = defaultdict(int)
    entry_ids: list[int] = []
    for row in rows:
        task_name = str(row["task_name"])
        grouped_seconds[task_name] += int(row["duration_seconds"])
        entry_ids.append(int(row["id"]))

    project_row = fetch_project(project_id)
    if project_row is None:
        return [], []

    hourly_rate = Decimal(str(project_row["hourly_rate"]))
    items: list[InvoiceLineItem] = []
    for task_name, total_seconds in grouped_seconds.items():
        rounded_hours = _round_seconds_to_quarter_hours(total_seconds)
        amount = (rounded_hours * hourly_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        items.append(InvoiceLineItem(task_name=task_name, raw_seconds=total_seconds, rounded_hours=rounded_hours, amount=amount))

    items.sort(key=lambda item: item.task_name.lower())
    return items, entry_ids


def generate_invoice_pdf(
    project_id: int,
    start_date: str,
    end_date: str,
    client_name: str,
    client_phone: str,
    client_address: str,
) -> Path:
    project_row = fetch_project(project_id)
    if project_row is None:
        raise ValueError("Selected project was not found")

    settings = fetch_settings()
    line_items, entry_ids = _group_invoice_items(project_id, start_date, end_date)
    if not line_items:
        raise ValueError("No billable time entries were found for the selected period")

    INVOICE_DIR.mkdir(parents=True, exist_ok=True)
    invoice_number = datetime.now().strftime("%Y%m%d%H%M%S")
    output_path = INVOICE_DIR / f"invoice-{invoice_number}.pdf"

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "InvoiceLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "InvoiceBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        spaceAfter=2,
    )
    small_style = ParagraphStyle(
        "InvoiceSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )

    project_rate = Decimal(str(project_row["hourly_rate"]))
    subtotal = sum((item.amount for item in line_items), Decimal("0.00"))

    story: list[object] = []
    logo_path = Path(str(settings["logo_path"]))
    if logo_path.exists() and logo_path.is_file():
        story.append(Image(str(logo_path), width=1.4 * inch, height=1.4 * inch, kind="proportional"))
        story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph(f"INVOICE # {invoice_number}", title_style))
    story.append(Paragraph(f"DATE: {date.today().isoformat()}", small_style))
    story.append(Spacer(1, 0.18 * inch))

    top_data = [
        [Paragraph("<b>Billed To</b>", label_style), Paragraph("<b>Bill From</b>", label_style)],
        [
            Paragraph(f"{client_name}<br/>{client_phone}<br/>{client_address}", body_style),
            Paragraph(
                f"{settings['bill_from_name']}<br/>{settings['bill_from_phone']}<br/>{settings['bill_from_address']}",
                body_style,
            ),
        ],
        [Paragraph("<b>Billing Period</b>", label_style), Paragraph(f"{start_date} - {end_date}", body_style)],
    ]
    top_table = Table(top_data, colWidths=[3.2 * inch, 3.2 * inch])
    top_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                ("LINEBELOW", (0, 1), (-1, 1), 0.25, colors.grey),
                ("LINEBELOW", (0, 2), (-1, 2), 0.5, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(top_table)
    story.append(Spacer(1, 0.24 * inch))

    story.append(Paragraph(str(project_row["name"]), ParagraphStyle("ProjectHeading", parent=styles["Heading2"], fontName="Helvetica-Bold", textColor=colors.HexColor("#111111"))))
    story.append(
        Paragraph(
            f"Rate: {project_rate:.2f}$/Hour - Billed in 15 minute Increments",
            small_style,
        )
    )
    story.append(Spacer(1, 0.12 * inch))

    table_data = [["Task", "Hours", "Amount"]]
    for item in line_items:
        table_data.append([item.task_name, _format_hours(item.rounded_hours), _format_money(item.amount)])
    table_data.append(["PROJECT SUBTOTAL |", "", _format_money(subtotal)])

    line_table = Table(table_data, colWidths=[3.6 * inch, 1.2 * inch, 1.6 * inch])
    line_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#cbd5e1")),
                ("GRID", (0, -1), (-1, -1), 0.75, colors.HexColor("#1f2937")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(line_table)
    story.append(Spacer(1, 0.18 * inch))

    footer_text = (
        f"Bank Name: {settings['bank_name']}<br/>"
        f"Account Name: {settings['account_name']}<br/>"
        f"Account Number: {settings['account_number']}"
    )
    story.append(Paragraph(footer_text, body_style))

    doc.build(story)
    mark_time_entries_invoiced(entry_ids)
    return output_path