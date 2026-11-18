"""Documento de reporte independiente del formato: una sola definición de datos y tres renderers."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.core.timeutil import fmt_date, fmt_datetime, to_local

# Tipos de columna: text | int | float | pct | datetime | date | ms | hours | minutes | bool | hash | json
HASH_PREFIX = 16


@dataclass
class Column:
    label: str
    kind: str = "text"
    width: float = 1.0          # peso relativo para el ancho en PDF y Word
    xlsx_only: bool = False     # columnas extensas (JSON, hash completo) que solo van en Excel


@dataclass
class Table:
    title: str
    columns: list[Column]
    rows: list[list[Any]]
    note: str | None = None
    total_rows: int | None = None   # total real cuando las filas se truncaron

    @property
    def truncated(self) -> bool:
        return self.total_rows is not None and self.total_rows > len(self.rows)


@dataclass
class ReportDocument:
    code: str
    title: str
    kind_label: str
    description: str
    header: str
    issued_at: datetime
    issued_by: str
    filters: list[tuple[str, str]]
    model_line: str | None
    is_demo: bool
    disclaimer: str | None
    summary: list[tuple[str, str]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return sum(len(t.rows) for t in self.tables)

    @property
    def full_title(self) -> str:
        return f"{self.code} · {self.title}"


DEMO_BAND = ("DEMO / NO VALIDADO: los diagnósticos de este reporte provienen de un modelo sin entrenar "
             "y no tienen valor diagnóstico.")


def fmt_number(v: float, decimals: int = 1) -> str:
    return f"{v:,.{decimals}f}".replace(",", " ")


def format_value(v: Any, kind: str) -> str:
    """Texto para PDF y Word (Excel conserva el tipo)."""
    if v is None or v == "":
        return "—"
    if kind == "pct":
        return f"{v * 100:.1f} %"
    if kind == "int":
        return f"{int(v):,}".replace(",", " ")
    if kind == "float":
        return fmt_number(float(v), 3)
    if kind == "hours":
        return f"{fmt_number(float(v), 1)} h"
    if kind == "minutes":
        return f"{fmt_number(float(v), 1)} min"
    if kind == "ms":
        return f"{int(round(v)):,} ms".replace(",", " ")
    if kind == "datetime":
        return fmt_datetime(v) if isinstance(v, datetime) else str(v)
    if kind == "date":
        return fmt_date(v) if isinstance(v, date) else str(v)
    if kind == "bool":
        return "Sí" if v else "No"
    if kind == "hash":
        s = str(v)
        return s[:HASH_PREFIX] + "…" if len(s) > HASH_PREFIX else s
    return str(v)


def excel_value(v: Any, kind: str) -> Any:
    if v is None:
        return None
    if kind == "datetime" and isinstance(v, datetime):
        return to_local(v).replace(tzinfo=None)
    if kind == "bool":
        return "Sí" if v else "No"
    if kind in ("int", "ms"):
        return int(round(v))
    if kind in ("float", "pct", "hours", "minutes"):
        return float(v)
    if kind == "json":
        import json

        return json.dumps(v, ensure_ascii=False, default=str)[:32000]
    return v


EXCEL_FORMATS = {
    "datetime": "dd/mm/yyyy hh:mm",
    "date": "dd/mm/yyyy",
    "pct": "0.0%",
    "float": "0.000",
    "hours": "0.0",
    "minutes": "0.0",
    "int": "#,##0",
    "ms": "#,##0",
}
