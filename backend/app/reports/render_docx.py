"""Word con python-docx: A4 horizontal, encabezado institucional y número de página en el pie."""

import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.core.timeutil import fmt_datetime
from app.reports.document import DEMO_BAND, ReportDocument, format_value

PRIMARY = RGBColor(0x2E, 0x7D, 0x32)
MUTED = RGBColor(0x61, 0x61, 0x61)
DEMO_FG = RGBColor(0xB7, 0x1C, 0x1C)
NUMERIC = {"int", "float", "pct", "ms", "hours", "minutes"}


def _shade(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def _page_number(paragraph) -> None:
    run = paragraph.add_run()
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), tag)
            run._r.append(fld)
        else:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = text
            run._r.append(instr)


def _cell_text(cell, text: str, *, bold: bool = False, size: float = 7.5, right: bool = False,
               color: RGBColor | None = None) -> None:
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    if right:
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color


def _kv(document, rows, width_cm: float) -> None:
    t = document.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for k, v in rows:
        cells = t.add_row().cells
        _cell_text(cells[0], k, bold=True, size=8.5)
        _shade(cells[0], "E8F5E9")
        _cell_text(cells[1], v, size=8.5)
        cells[0].width = Cm(width_cm * 0.3)
        cells[1].width = Cm(width_cm * 0.7)


def render_docx(doc: ReportDocument) -> bytes:
    d = Document()
    section = d.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin"):
        setattr(section, side, Cm(1.6))
    section.top_margin, section.bottom_margin = Cm(1.5), Cm(1.5)
    usable = 29.7 - 3.2

    normal = d.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(9.5)

    header = section.header.paragraphs[0]
    header.text = doc.header + ("    ·    DEMO / NO VALIDADO" if doc.is_demo else "")
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = DEMO_FG if doc.is_demo else MUTED
    footer = section.footer.paragraphs[0]
    footer.text = f"{doc.full_title} · Emitido: {fmt_datetime(doc.issued_at)} (hora de Lima) · Página "
    footer.runs[0].font.size = Pt(8)
    _page_number(footer)

    title = d.add_heading(doc.full_title, level=1)
    for r in title.runs:
        r.font.color.rgb = PRIMARY
    p = d.add_paragraph(f"Reporte {doc.kind_label.lower()} · {doc.description}")
    p.runs[0].font.color.rgb = MUTED

    meta = [("Fecha de emisión", f"{fmt_datetime(doc.issued_at)} (America/Lima)"), ("Emitido por", doc.issued_by)]
    if doc.model_line:
        meta.append(("Versión del modelo", doc.model_line))
    meta.append(("Filtros aplicados", "; ".join(f"{k}: {v}" for k, v in doc.filters) or "Ninguno"))
    _kv(d, meta, usable)

    if doc.is_demo:
        band = d.add_table(rows=1, cols=1)
        band.style = "Table Grid"
        _cell_text(band.rows[0].cells[0], DEMO_BAND, bold=True, size=9.5, color=DEMO_FG)
        _shade(band.rows[0].cells[0], "FDECEA")

    if doc.summary:
        d.add_heading("Resumen", level=2)
        _kv(d, doc.summary, usable * 0.6)

    for table in doc.tables:
        d.add_heading(table.title, level=2)
        cols = [(i, c) for i, c in enumerate(table.columns) if not c.xlsx_only]
        if not table.rows:
            d.add_paragraph("Sin datos para los filtros seleccionados.").runs[0].font.color.rgb = MUTED
            continue
        t = d.add_table(rows=1, cols=len(cols))
        t.style = "Table Grid"
        total_w = sum(c.width for _, c in cols)
        hdr = t.rows[0]
        _repeat_header(hdr)
        for cell, (_, c) in zip(hdr.cells, cols, strict=True):
            _cell_text(cell, c.label, bold=True)
            _shade(cell, "E8F5E9")
        for row in table.rows:
            cells = t.add_row().cells
            for cell, (i, c) in zip(cells, cols, strict=True):
                _cell_text(cell, format_value(row[i], c.kind), right=c.kind in NUMERIC)
        for row in t.rows:
            for cell, (_, c) in zip(row.cells, cols, strict=True):
                cell.width = Cm(usable * c.width / total_w)
        if table.note:
            n = d.add_paragraph(table.note)
            n.runs[0].font.size = Pt(8)
            n.runs[0].font.color.rgb = MUTED

    if doc.notes:
        d.add_heading("Notas", level=2)
        for note in doc.notes:
            d.add_paragraph(note, style="List Bullet").runs[0].font.size = Pt(8.5)
    if doc.disclaimer:
        p = d.add_paragraph(doc.disclaimer)
        p.runs[0].italic = True
        p.runs[0].font.size = Pt(8.5)
        p.runs[0].font.color.rgb = MUTED

    props = d.core_properties
    props.title = doc.full_title
    props.author = doc.issued_by[:250]
    props.subject = doc.description
    out = io.BytesIO()
    d.save(out)
    return out.getvalue()
