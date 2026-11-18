"""Excel con openpyxl en modo de escritura en flujo (write_only): poca memoria aun con 50 000 filas.

Hoja "Resumen" con el encabezado del reporte y una hoja por tabla con valores tipados.
"""

import io
import re

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.core.timeutil import fmt_datetime
from app.reports.document import DEMO_BAND, EXCEL_FORMATS, ReportDocument, excel_value

HEADER_FILL = PatternFill("solid", fgColor="E8F5E9")
DEMO_FILL = PatternFill("solid", fgColor="FDECEA")
BOLD = Font(bold=True)
TITLE = Font(bold=True, size=14, color="2E7D32")
SECTION = Font(bold=True, size=12, color="2E7D32")
DEMO_FONT = Font(bold=True, color="B71C1C")
MUTED = Font(color="616161", italic=True)
WRAP = Alignment(wrap_text=True, vertical="top")
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(v):
    return _ILLEGAL.sub("", v) if isinstance(v, str) else v


def _sheet_name(title: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "-", title)[:28] or "Datos"
    name, n = base, 2
    while name.lower() in used:
        name = f"{base[:25]} ({n})"
        n += 1
    used.add(name.lower())
    return name


def _cell(ws, value, font=None, fill=None, fmt=None, wrap=False) -> WriteOnlyCell:
    c = WriteOnlyCell(ws, value=_clean(value))
    if font is not None:
        c.font = font
    if fill is not None:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if wrap:
        c.alignment = WRAP
    return c


def render_xlsx(doc: ReportDocument) -> bytes:
    wb = Workbook(write_only=True)
    used = {"resumen"}
    ws = wb.create_sheet("Resumen")
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 95

    def kv(key, value, key_font=BOLD, value_font=None):
        ws.append([_cell(ws, key, key_font), _cell(ws, value, value_font, wrap=True)])

    ws.append([_cell(ws, doc.header, MUTED)])
    ws.append([_cell(ws, doc.full_title, TITLE)])
    ws.append([_cell(ws, doc.description)])
    ws.append([])
    kv("Tipo de reporte", doc.kind_label)
    kv("Fecha de emisión", f"{fmt_datetime(doc.issued_at, seconds=True)} (America/Lima)")
    kv("Emitido por", doc.issued_by)
    if doc.model_line:
        kv("Versión del modelo", doc.model_line)
    kv("Filtros aplicados", "; ".join(f"{k}: {v}" for k, v in doc.filters) or "Ninguno")
    if doc.is_demo:
        ws.append([])
        ws.append([_cell(ws, DEMO_BAND, DEMO_FONT, DEMO_FILL), _cell(ws, None, fill=DEMO_FILL)])
    if doc.summary:
        ws.append([])
        ws.append([_cell(ws, "Resumen", SECTION)])
        for k, v in doc.summary:
            kv(k, v)
    ws.append([])
    ws.append([_cell(ws, "Hojas", SECTION)])
    sheets = []
    for table in doc.tables:
        name = _sheet_name(table.title, used)
        kv(name, f"{table.title} ({len(table.rows)} filas)", key_font=None)
        sheets.append((name, table))
    if doc.notes:
        ws.append([])
        for n in doc.notes:
            ws.append([None, _cell(ws, n, MUTED, wrap=True)])
    if doc.disclaimer:
        ws.append([])
        ws.append([None, _cell(ws, doc.disclaimer, MUTED, wrap=True)])

    for name, table in sheets:
        sh = wb.create_sheet(name)
        # Ancho de columnas y paneles fijos: deben definirse antes de escribir filas en modo write_only
        for j, col in enumerate(table.columns, start=1):
            min_width = 17 if col.kind == "datetime" else 12
            sh.column_dimensions[get_column_letter(j)].width = 60 if col.kind == "json" else min(
                48, max(min_width, len(col.label) + 4, 12 * col.width + 6))
        sh.freeze_panes = "A2"
        if table.rows:
            sh.auto_filter.ref = f"A1:{get_column_letter(len(table.columns))}{len(table.rows) + 1}"
        sh.append([_cell(sh, c.label, BOLD, HEADER_FILL) for c in table.columns])
        formats = [EXCEL_FORMATS.get(c.kind) for c in table.columns]
        for row in table.rows:
            sh.append([_cell(sh, excel_value(v, c.kind), fmt=f) if f else _clean(excel_value(v, c.kind))
                       for v, c, f in zip(row, table.columns, formats, strict=True)])
        if table.note:
            sh.append([])
            sh.append([_cell(sh, table.note, MUTED)])
        if not table.rows:
            sh.append([_cell(sh, "Sin datos para los filtros seleccionados.", MUTED)])

    wb.properties.title = doc.full_title
    wb.properties.creator = doc.issued_by[:250]
    wb.properties.subject = doc.description
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
