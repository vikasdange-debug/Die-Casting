"""Dependency-free, locally generated PDF reports for one CAD analysis."""
from __future__ import annotations

import math
import re
import unicodedata


PAGE_WIDTH, PAGE_HEIGHT = 612, 792
NAVY = (0.09, 0.22, 0.27)
TEAL = (0.13, 0.43, 0.38)
INK = (0.14, 0.23, 0.26)
MUTED = (0.38, 0.46, 0.48)
PALE = (0.95, 0.97, 0.96)
GOLD_BG = (0.98, 0.96, 0.90)
GOLD_INK = (0.38, 0.31, 0.14)
RULE = (0.84, 0.89, 0.87)


def _ascii(text):
    return unicodedata.normalize("NFKD", str(text).replace("°", " deg ")).encode("ascii", "ignore").decode("ascii")


def _safe(text):
    value = _ascii(text)
    value = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return re.sub(r"[^\x20-\x7e]", "?", value)


def _wrap(text, width=92):
    """Wrap text, including long filenames and other unbroken input tokens."""
    words = _ascii(text).split()
    lines, current = [], ""
    for raw_word in words:
        word = raw_word
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if len(current) + len(word) + bool(current) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines or [""]


class _ReportLayout:
    def __init__(self, title):
        self.title = title
        self.pages = []
        self.y = 0
        self.new_page(first=True)

    @staticmethod
    def _rgb(color):
        return " ".join(f"{part:.3f}" for part in color)

    def rect(self, x, y, width, height, fill, stroke=None):
        op = ["q", f"{self._rgb(fill)} rg", f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re f"]
        if stroke:
            op += [f"{self._rgb(stroke)} RG", f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re S"]
        op.append("Q")
        self.pages[-1].extend(op)

    def text(self, x, y, value, *, size=9, bold=False, color=INK):
        font = "/F2" if bold else "/F1"
        self.pages[-1].append(
            f"BT {font} {size:.2f} Tf {self._rgb(color)} rg 1 0 0 1 {x:.2f} {y:.2f} Tm ({_safe(value)}) Tj ET"
        )

    def new_page(self, *, first=False):
        self.pages.append([])
        self.rect(0, 718, PAGE_WIDTH, 74, NAVY)
        self.text(42, 765, "HPDC SMART PROCESS ADVISOR", size=8, bold=True, color=(0.77, 0.87, 0.84))
        self.text(42, 739, self.title if first else f"{self.title} | continued", size=19, bold=True, color=(1, 1, 1))
        self.y = 698

    def ensure_space(self, height):
        if self.y - height < 48:
            self.new_page()

    def section(self, title):
        self.ensure_space(24)
        self.text(42, self.y, title.upper(), size=9, bold=True, color=TEAL)
        self.pages[-1].append(f"q {self._rgb(RULE)} RG 42 {self.y - 6:.2f} m 570 {self.y - 6:.2f} l S Q")
        self.y -= 20

    def paragraph(self, text, *, width=92, size=8.5, leading=12, color=INK, x=42):
        lines = _wrap(text, width)
        self.ensure_space(len(lines) * leading + 2)
        for line in lines:
            self.text(x, self.y, line, size=size, color=color)
            self.y -= leading
        self.y -= 2

    def parameter_cards(self, predictions):
        self.section("HPDC process parameter estimates")
        card_width, card_height, gap_x, gap_y = 256, 67, 16, 8
        range_warnings = []
        for index, item in enumerate(predictions):
            column, row = index % 2, index // 2
            if column == 0:
                self.ensure_space(card_height + (gap_y if row else 0))
            row_top = self.y
            x = 42 + column * (card_width + gap_x)
            bottom = row_top - card_height
            self.rect(x, bottom, card_width, card_height, PALE, RULE)
            self.text(x + 11, bottom + 51, item.get("label", item.get("name", "Parameter")), size=8.5, bold=True)
            value = str(item.get("value", "Unavailable"))
            unit = str(item.get("unit", ""))
            self.text(x + 11, bottom + 31, f"{value} {unit}".strip(), size=14, bold=True, color=NAVY)
            desc_lines = _wrap(item.get("description", "Model estimate."), 48)
            self.text(x + 11, bottom + 14, desc_lines[0], size=7.2, color=MUTED)
            if len(desc_lines) > 1:
                self.text(x + 11, bottom + 5, desc_lines[1], size=7.2, color=MUTED)
            warning = item.get("range_warning")
            if warning:
                range_warnings.append(f"{item.get('label', 'Parameter')}: {warning}")
            if column == 1:
                self.y -= card_height + gap_y
        if len(predictions) % 2:
            self.y -= card_height + gap_y
        self.y -= 9
        for warning in range_warnings:
            self.paragraph(f"Range warning: {warning}", width=92, size=8, color=GOLD_INK)

    def finish(self):
        total = len(self.pages)
        for index, page in enumerate(self.pages, start=1):
            page += ["q", f"{self._rgb(RULE)} RG", "42 37 m 570 37 l S", "Q"]
            page.append(
                f"BT /F1 7 Tf {self._rgb(MUTED)} rg 1 0 0 1 42 23 Tm "
                f"(Prototype estimates require qualified engineering review.) Tj ET"
            )
            page.append(
                f"BT /F1 7 Tf {self._rgb(MUTED)} rg 1 0 0 1 535 23 Tm ({index} / {total}) Tj ET"
            )
        return _serialize_pdf(self.pages)


def _serialize_pdf(page_commands):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    page_ids = []
    for commands in page_commands:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        stream = "\n".join(commands).encode("ascii")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{pid} 0 R' for pid in page_ids)}] /Count {len(page_ids)} >>".encode()
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


def _fallback_analysis_pdf(result):
    model = result.get("metadata") or {}
    layout = _ReportLayout("Analysis report")

    layout.text(42, layout.y, "COMPONENT", size=7.5, bold=True, color=TEAL)
    component_lines = _wrap(result.get("filename", "Unknown component"), 68)
    for line in component_lines:
        layout.text(122, layout.y, line, size=9, bold=True)
        layout.y -= 11
    layout.y -= 4
    layout.text(42, layout.y, "ANALYZED (UTC)", size=7.5, bold=True, color=TEAL)
    layout.text(122, layout.y, result.get("created_at", "Not recorded"), size=8.5)
    layout.y -= 20

    warning = (
        "SYNTHETIC DATA PROTOTYPE: estimates demonstrate the software pipeline only. "
        "They are not validated for real production or machine setup."
    ) if result.get("predictions") else "PARAMETER ESTIMATION UNAVAILABLE: no valid model estimate was generated."
    warning_lines = _wrap(warning, 92)
    warning_height = 18 + 12 * len(warning_lines)
    layout.rect(42, layout.y - warning_height + 5, 528, warning_height, GOLD_BG, (0.90, 0.84, 0.66))
    for line_index, line in enumerate(warning_lines):
        layout.text(54, layout.y - 10 - line_index * 12, line, size=8.5, bold=line_index == 0, color=GOLD_INK)
    layout.y -= warning_height + 8

    if result.get("predictions"):
        layout.parameter_cards(result["predictions"])
    else:
        layout.section("HPDC process parameter estimates")
        layout.paragraph("No valid model estimates were generated. Review the application status and configure a compatible trained model.")

    layout.section("Model and data provenance")
    layout.paragraph(f"Model: {model.get('model_version', 'unavailable')} ({model.get('model_kind', 'not loaded')}).", width=98)
    layout.paragraph(f"Dataset: {model.get('dataset_provenance', 'unavailable')}.", width=98)
    layout.paragraph(f"Training date: {model.get('training_date_utc', 'unavailable')}; validation: {model.get('validation_method', 'not available')}.", width=98)
    if model.get("input_out_of_training_range"):
        layout.paragraph("Coverage warning: one or more CAD features fall outside synthetic training ranges; outputs are extrapolations.", width=96, color=GOLD_INK)
    metrics = model.get("metrics") or {}
    if metrics:
        layout.paragraph("Holdout errors (synthetic only; values use each target's unit):", width=98, size=8, color=MUTED)
        metric_summary = " | ".join(
            f"{name.replace('_', ' ')} MAE {values.get('mae', 'n/a'):.4g}"
            for name, values in metrics.items() if isinstance(values.get("mae"), (int, float)) and math.isfinite(values["mae"])
        )
        if metric_summary:
            layout.paragraph(metric_summary, width=98, size=7.5, color=MUTED)

    layout.section("Engineering notes")
    limitation_added = False
    for warning_text in result.get("warnings", []):
        if warning_text.startswith("Prototype model trained on synthetic data"):
            continue  # Already shown in the prominent report status banner.
        if warning_text.startswith("Validate process estimates with a qualified HPDC engineer"):
            continue  # The report footer already repeats the review requirement.
        if warning_text.startswith("Wall thickness is not automatically measured") or warning_text.startswith("Basic geometric extraction does not assess"):
            if limitation_added:
                continue
            warning_text = "Not assessed: wall thickness, draft/undercuts, defects, filling/solidification simulation, quality prediction, machine limits, or optimization."
            limitation_added = True
        layout.paragraph(f"- {warning_text}", width=98, size=8, leading=11, color=INK)
    if result.get("nominal_thickness_mm") is not None:
        layout.paragraph(
            f"- User-supplied nominal wall thickness: {result['nominal_thickness_mm']:g} mm. "
            "It is not measured from CAD and is not a model input.", width=98, size=8, leading=11,
        )
    return layout.finish()


def _reportlab_analysis_pdf(result):
    """Build the styled report with ReportLab when the requested package exists."""
    from io import BytesIO
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ink = colors.HexColor("#243b43")
    teal = colors.HexColor("#246d62")
    muted = colors.HexColor("#62777c")
    pale = colors.HexColor("#eff4f2")
    gold = colors.HexColor("#fbf3df")
    gold_ink = colors.HexColor("#5e4b1e")
    rule = colors.HexColor("#d6e2de")

    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("HPDCTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=21,
                                 leading=25, textColor=colors.HexColor("#173744"), alignment=TA_LEFT, spaceAfter=4),
        "eyebrow": ParagraphStyle("HPDCEyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
                                   leading=10, textColor=teal, spaceBefore=4, spaceAfter=6),
        "body": ParagraphStyle("HPDCBody", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5,
                                leading=12, textColor=ink),
        "small": ParagraphStyle("HPDCSmall", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5,
                                 leading=10, textColor=muted),
        "label": ParagraphStyle("HPDCLabel", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8,
                                 leading=10, textColor=ink),
        "value": ParagraphStyle("HPDCValue", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=10,
                                 leading=12, textColor=colors.HexColor("#173744")),
        "warning": ParagraphStyle("HPDCWarning", parent=base["BodyText"], fontName="Helvetica", fontSize=8.5,
                                   leading=12, textColor=gold_ink),
    }

    def para(value, style="body"):
        return Paragraph(escape(str(value)), styles[style])

    buffer = BytesIO()

    def page_footer(canvas, document):
        canvas.saveState()
        width, _height = letter
        canvas.setFillColor(colors.HexColor("#173744"))
        canvas.rect(0, _height - 7 * mm, width, 7 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.white)
        canvas.drawString(15 * mm, _height - 4.8 * mm, "HPDC SMART PROCESS ADVISOR")
        canvas.setStrokeColor(rule)
        canvas.line(15 * mm, 13 * mm, width - 15 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(15 * mm, 8 * mm, "Prototype estimates require qualified engineering review.")
        canvas.drawRightString(width - 15 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=15 * mm, leftMargin=15 * mm,
                                 topMargin=14 * mm, bottomMargin=19 * mm,
                                 title="HPDC Smart Process Advisor Analysis Report",
                                 author="HPDC Smart Process Advisor")
    story = [para("HPDC SMART PROCESS ADVISOR", "eyebrow"), para("Analysis report", "title"), Spacer(1, 5)]

    meta = [
        [para("COMPONENT", "eyebrow"), para(result.get("filename", "Unknown component"), "label")],
        [para("ANALYZED (UTC)", "eyebrow"), para(result.get("created_at", "Not recorded"), "body")],
        [para("STATUS", "eyebrow"), para(result.get("status", "Not recorded"), "body")],
    ]
    meta_table = Table(meta, colWidths=[31 * mm, 147 * mm], hAlign="LEFT")
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [meta_table, Spacer(1, 6)]

    has_predictions = bool(result.get("predictions"))
    notice = ("SYNTHETIC DATA PROTOTYPE: these estimates demonstrate the software pipeline only. "
              "They are not validated for real production or machine setup." if has_predictions else
              "PARAMETER ESTIMATION UNAVAILABLE: no valid model estimate was generated.")
    notice_table = Table([[para(notice, "warning")]], colWidths=[178 * mm])
    notice_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), gold), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e4d5aa")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [notice_table, Spacer(1, 10), para("HPDC PROCESS PARAMETER ESTIMATES", "eyebrow")]

    if has_predictions:
        rows = [[para("PARAMETER", "label"), para("ESTIMATE", "label"), para("UNIT", "label"), para("MEANING", "label")]]
        for item in result["predictions"]:
            description = item.get("description", "Model estimate.")
            if item.get("range_warning"):
                description += " Warning: " + item["range_warning"]
            rows.append([para(item.get("label", item.get("name", "Parameter")), "label"),
                         para(item.get("value", "Unavailable"), "value"),
                         para(item.get("unit", ""), "body"), para(description, "small")])
        params = Table(rows, colWidths=[42 * mm, 28 * mm, 24 * mm, 84 * mm], repeatRows=1, hAlign="LEFT")
        params.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), pale), ("TEXTCOLOR", (0, 0), (-1, 0), teal),
            ("GRID", (0, 0), (-1, -1), 0.35, rule), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale]),
        ]))
        story += [params, Spacer(1, 10)]
    else:
        story += [para("No valid model estimates were generated. Configure a compatible trained model and retry."), Spacer(1, 8)]

    model = result.get("metadata") or {}
    story += [para("MODEL AND DATA PROVENANCE", "eyebrow")]
    provenance = [
        [para("Model", "label"), para(f"{model.get('model_version', 'unavailable')} ({model.get('model_kind', 'not loaded')})")],
        [para("Dataset", "label"), para(model.get("dataset_provenance", "unavailable"))],
        [para("Training / validation", "label"), para(f"{model.get('training_date_utc', 'not recorded')} / {model.get('validation_method', 'not available')}")],
    ]
    if model.get("input_out_of_training_range"):
        provenance.append([para("Coverage", "label"), para("CAD features extend outside synthetic training ranges; treat predictions as extrapolations.", "warning")])
    provenance_table = Table(provenance, colWidths=[37 * mm, 141 * mm], hAlign="LEFT")
    provenance_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.35, rule),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [provenance_table]

    metrics = model.get("metrics") or {}
    if metrics:
        story += [Spacer(1, 6), para("SYNTHETIC HOLDOUT ERRORS (not real HPDC performance)", "eyebrow")]
        metric_rows = [[para("TARGET", "label"), para("MAE", "label"), para("RMSE", "label"), para("UNIT", "label")]]
        for target, values in metrics.items():
            if not isinstance(values, dict):
                continue
            mae, rmse = values.get("mae"), values.get("rmse")
            if all(isinstance(value, (int, float)) and math.isfinite(value) for value in (mae, rmse)):
                unit = model.get("target_units", {}).get(target, "target unit")
                metric_rows.append([para(target.replace("_", " "), "small"), para(f"{mae:.4g}", "small"),
                                    para(f"{rmse:.4g}", "small"), para(unit, "small")])
        if len(metric_rows) > 1:
            metric_table = Table(metric_rows, colWidths=[80 * mm, 30 * mm, 30 * mm, 38 * mm], repeatRows=1, hAlign="LEFT")
            metric_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), pale), ("GRID", (0, 0), (-1, -1), 0.35, rule),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(metric_table)

    note_section = [para("ENGINEERING NOTES", "eyebrow")]
    for warning_text in result.get("warnings", []):
        if warning_text.startswith("Prototype model trained on synthetic data"):
            continue
        if warning_text.startswith("Wall thickness is not automatically measured"):
            warning_text = "Wall thickness is not measured; review thin sections and transitions with a suitable validated tool."
        elif warning_text.startswith("Basic geometric extraction does not assess"):
            warning_text = "Draft, undercuts, defects, filling, and solidification are not assessed."
        note_section.append(para("- " + warning_text))
    if result.get("nominal_thickness_mm") is not None:
        note_section.append(para(f"- User-supplied nominal wall thickness: {result['nominal_thickness_mm']:g} mm; not measured from CAD and not a model input."))
    note_section.append(para("- No quality prediction, validated operating range, or optimization is provided.", "small"))
    story += [Spacer(1, 8), KeepTogether(note_section)]

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()


def analysis_pdf(result):
    """Prefer ReportLab, retaining a tested dependency-free fallback for offline installs."""
    try:
        return _reportlab_analysis_pdf(result)
    except ImportError:
        return _fallback_analysis_pdf(result)
