"""PDF con ReportLab (docs/decisiones.md D-41): A4 horizontal, encabezado y pie en cada página."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.timeutil import fmt_datetime
from app.reports.document import DEMO_BAND, ReportDocument, format_value

PRIMARY = colors.HexColor("#2e7d32")
HEADER_BG = colors.HexColor("#e8f5e9")
DEMO_BG = colors.HexColor("#fdecea")
DEMO_FG = colors.HexColor("#b71c1c")
GRID = colors.HexColor("#bdbdbd")
MUTED = colors.HexColor("#616161")


def _t(text) -> str:
    """Escapa XML y reemplaza los caracteres que las fuentes estándar (WinAnsi) no pueden dibujar."""
    s = escape(str(text))
    return s.encode("cp1252", "replace").decode("cp1252")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=15, leading=19, alignment=0, spaceAfter=2,
                                textColor=PRIMARY),
        "inst": ParagraphStyle("i", parent=base["Normal"], fontSize=9, textColor=MUTED),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, leading=14, spaceBefore=10, spaceAfter=4,
                             textColor=PRIMARY),
        "body": ParagraphStyle("b", parent=base["Normal"], fontSize=8.5, leading=11),
        "cell": ParagraphStyle("c", parent=base["Normal"], fontSize=7.3, leading=9),
        "cellr": ParagraphStyle("cr", parent=base["Normal"], fontSize=7.3, leading=9, alignment=TA_RIGHT),
        "head": ParagraphStyle("h", parent=base["Normal"], fontSize=7.3, leading=9, fontName="Helvetica-Bold"),
        "note": ParagraphStyle("n", parent=base["Normal"], fontSize=7.5, leading=10, textColor=MUTED),
        "demo": ParagraphStyle("d", parent=base["Normal"], fontSize=9, leading=12, textColor=DEMO_FG,
                               fontName="Helvetica-Bold"),
    }


NUMERIC = {"int", "float", "pct", "ms", "hours", "minutes"}


def render_pdf(doc: ReportDocument) -> bytes:
    st = _styles()
    buf = io.BytesIO()
    page = landscape(A4)
    margin = 1.4 * cm
    width = page[0] - 2 * margin

    def on_page(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 0.8 * cm, _t(f"{doc.header} · {doc.full_title}")[:150])
        canvas.drawRightString(page[0] - margin, 0.8 * cm, f"Página {d.page}")
        canvas.drawRightString(page[0] - margin, 0.5 * cm, _t(f"Emitido: {fmt_datetime(doc.issued_at)} (hora de Lima)"))
        if doc.is_demo:
            canvas.setFillColor(DEMO_FG)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawRightString(page[0] - margin, page[1] - 0.8 * cm, "DEMO / NO VALIDADO")
        canvas.restoreState()

    story = [Paragraph(_t(doc.header), st["inst"]), Paragraph(_t(doc.full_title), st["title"]),
             Paragraph(_t(f"Reporte {doc.kind_label.lower()} · {doc.description}"), st["body"]), Spacer(1, 6)]

    meta = [("Fecha de emisión", f"{fmt_datetime(doc.issued_at)} (America/Lima)"), ("Emitido por", doc.issued_by)]
    if doc.model_line:
        meta.append(("Versión del modelo", doc.model_line))
    meta.append(("Filtros aplicados", "; ".join(f"{k}: {v}" for k, v in doc.filters) or "Ninguno"))
    story.append(_kv_table(meta, width, st))
    if doc.is_demo:
        band = Table([[Paragraph(_t(DEMO_BAND), st["demo"])]], colWidths=[width])
        band.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), DEMO_BG), ("BOX", (0, 0), (-1, -1), 1, DEMO_FG),
                                  ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [Spacer(1, 6), band]

    if doc.summary:
        story += [Paragraph("Resumen", st["h2"]), _kv_table(doc.summary, width * 0.6, st)]

    for table in doc.tables:
        cols = [c for c in table.columns if not c.xlsx_only]
        idx = [i for i, c in enumerate(table.columns) if not c.xlsx_only]
        title = Paragraph(_t(table.title), st["h2"])
        if not table.rows:
            story.append(KeepTogether([title, Paragraph("Sin datos para los filtros seleccionados.", st["note"])]))
            continue
        total_w = sum(c.width for c in cols)
        widths = [width * c.width / total_w for c in cols]
        data = [[Paragraph(_t(c.label), st["head"]) for c in cols]]
        for row in table.rows:
            data.append([Paragraph(_t(format_value(row[i], c.kind)), st["cellr" if c.kind in NUMERIC else "cell"])
                         for i, c in zip(idx, cols, strict=True)])
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story += [title, t]
        if table.note:
            story.append(Paragraph(_t(table.note), st["note"]))

    if doc.notes:
        story.append(Paragraph("Notas", st["h2"]))
        story += [Paragraph(_t(f"• {n}"), st["note"]) for n in doc.notes]
    if doc.disclaimer:
        story += [Spacer(1, 8), Paragraph(_t(doc.disclaimer), st["note"])]

    pdf = SimpleDocTemplate(buf, pagesize=page, leftMargin=margin, rightMargin=margin, topMargin=1.3 * cm,
                            bottomMargin=1.4 * cm, title=doc.full_title, author=doc.issued_by,
                            subject=doc.description, creator="PapaSana AP-01")
    pdf.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _kv_table(rows, width, st) -> Table:
    data = [[Paragraph(_t(k), st["head"]), Paragraph(_t(v), st["cell"])] for k, v in rows]
    t = Table(data, colWidths=[width * 0.28, width * 0.72])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, GRID), ("BACKGROUND", (0, 0), (0, -1), HEADER_BG),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    t.hAlign = "LEFT"
    return t
