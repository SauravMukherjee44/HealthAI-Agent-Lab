from datetime import UTC, datetime
from io import BytesIO
from typing import Any

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = (
    "This educational screening result is not a diagnosis, medical advice, or a substitute for professional care."
)


def _display_name(name: str) -> str:
    return name.replace("_", " ").title()


def build_pdf(report: dict[str, Any], alias: str | None) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="HealthAI screening report",
        author="HealthAI Agent Lab",
    )
    styles = getSampleStyleSheet()
    brand = ParagraphStyle(
        "Brand",
        parent=styles["Title"],
        textColor=colors.HexColor("#075e54"),
        fontSize=24,
        leading=28,
        alignment=TA_LEFT,
    )
    heading = ParagraphStyle(
        "Heading", parent=styles["Heading2"], textColor=colors.HexColor("#173f3a"), spaceBefore=10, spaceAfter=7
    )
    body = ParagraphStyle(
        "Body", parent=styles["BodyText"], fontSize=9.5, leading=14, textColor=colors.HexColor("#294944")
    )
    story = [
        Paragraph("Health<span color='#16a67a'>AI</span>", brand),
        Paragraph("Agent Lab · Educational screening report", body),
        Spacer(1, 7 * mm),
        Paragraph(f"{_display_name(report['condition'])} screening", styles["Heading1"]),
    ]
    summary = [
        ["Prepared for", alias or "Anonymous"],
        ["Generated", datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")],
        ["Screening band", report["band"].title()],
        ["Model version", report["model_version"]],
        ["Validation status", report["validation_status"].title()],
    ]
    table = Table(summary, colWidths=[42 * mm, 110 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9f7f3")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#173f3a")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8d8d1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([table, Paragraph("Confirmed inputs", heading)])
    input_rows = [[_display_name(name), str(value)] for name, value in report["inputs"].items()]
    input_table = Table(input_rows, colWidths=[80 * mm, 72 * mm], repeatRows=0)
    input_table.setStyle(
        TableStyle(
            [
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f6faf9")]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d5e5e1")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(input_table)
    story.append(Paragraph("Interpretation", heading))
    result_text = (
        "The model found an elevated pattern in the confirmed inputs. This does not establish that a condition is present."
        if report["band"] == "elevated"
        else "The model did not find an elevated pattern in the confirmed inputs. This does not rule out a condition."
    )
    story.append(Paragraph(result_text, body))
    story.append(Paragraph("Limitations", heading))
    for limitation in report.get("limitations", []):
        story.append(Paragraph(f"• {limitation}", body))
    story.extend(
        [
            Paragraph("Next step", heading),
            Paragraph(
                "Discuss persistent symptoms, concerns, or unexpected results with a qualified clinician. For severe or sudden symptoms, call India emergency services at 112.",
                body,
            ),
            Spacer(1, 5 * mm),
            Table(
                [[Paragraph(f"<b>Important:</b> {DISCLAIMER}", body)]],
                colWidths=[152 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff5e8")),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e8a34b")),
                        ("PADDING", (0, 0), (-1, -1), 9),
                    ]
                ),
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()


def build_xlsx(report: dict[str, Any], alias: str | None) -> bytes:
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    title = workbook.add_format({"bold": True, "font_size": 18, "font_color": "#075e54"})
    header = workbook.add_format({"bold": True, "bg_color": "#DFF4EE", "border": 1, "font_color": "#173F3A"})
    cell = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    warning = workbook.add_format({"bg_color": "#FFF5E8", "font_color": "#7A4914", "text_wrap": True, "border": 1})

    summary = workbook.add_worksheet("Summary")
    summary.set_column("A:A", 24)
    summary.set_column("B:B", 70)
    summary.write("A1", "HealthAI Screening Report", title)
    summary_rows = [
        ("Prepared for", alias or "Anonymous"),
        ("Condition", _display_name(report["condition"])),
        ("Screening band", report["band"].title()),
        ("Probability", report.get("probability")),
        ("Threshold", report.get("threshold")),
        ("Model version", report["model_version"]),
        ("Validation status", report["validation_status"]),
    ]
    for row, (label, value) in enumerate(summary_rows, start=2):
        summary.write(row, 0, label, header)
        summary.write(row, 1, value, cell)
    summary.merge_range(11, 0, 12, 1, DISCLAIMER, warning)

    inputs = workbook.add_worksheet("Confirmed Inputs")
    inputs.set_column("A:A", 34)
    inputs.set_column("B:B", 24)
    inputs.write_row(0, 0, ["Input", "Confirmed value"], header)
    for row, (name, value) in enumerate(report["inputs"].items(), start=1):
        inputs.write(row, 0, _display_name(name), cell)
        inputs.write(row, 1, value, cell)

    provenance = workbook.add_worksheet("Provenance & Limitations")
    provenance.set_column("A:A", 28)
    provenance.set_column("B:B", 90)
    provenance.write_row(0, 0, ["Item", "Details"], header)
    provenance.write_row(1, 0, ["Model version", report["model_version"]], cell)
    provenance.write_row(2, 0, ["Validation status", report["validation_status"]], cell)
    provenance.write_row(3, 0, ["Dataset", str(report.get("dataset", {}))], cell)
    for row, limitation in enumerate(report.get("limitations", []), start=4):
        provenance.write(row, 0, f"Limitation {row - 3}", header)
        provenance.write(row, 1, limitation, cell)
    workbook.close()
    return buffer.getvalue()
