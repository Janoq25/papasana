"""Catálogo de reportes (docs/fase0_plan.md §8): código, permisos requeridos, filtros y constructor."""

from collections.abc import Callable
from dataclasses import dataclass

from app.reports import builders as b
from app.reports.builders import BuildContext, BuildResult

KIND_LABELS = {"operacional": "Operacional", "gestion": "Gestión", "auditoria": "Auditoría"}
EXPORT = "reportes:exportar"
AUDIT_VIEW = "bitacora:ver"


@dataclass(frozen=True)
class ReportDef:
    code: str
    title: str
    kind: str
    description: str
    filters: tuple[str, ...]
    permissions: tuple[str, ...]
    builder: Callable[[BuildContext], BuildResult]
    uses_model: bool = True       # muestra la versión del modelo, la franja DEMO y el aviso profesional
    available_from_phase: int | None = None


REPORTS: dict[str, ReportDef] = {r.code: r for r in [
    ReportDef("R-01", "Diagnósticos por fecha, parcela y técnico", "operacional",
              "Detalle y resumen de los diagnósticos realizados, por técnico y por parcela.",
              ("date_from", "date_to", "region_code", "parcel_id", "technician_id", "category", "status"),
              (EXPORT,), b.build_r01),
    ReportDef("R-02", "Imágenes procesadas", "operacional",
              "Fotografías recibidas con su procedencia, ubicación GPS y posibles duplicados.",
              ("date_from", "date_to", "region_code", "parcel_id", "batch_id", "provenance"),
              (EXPORT,), b.build_r02),
    ReportDef("R-03", "Casos pendientes de revisión", "operacional",
              "Diagnósticos en la bandeja del especialista, de los más antiguos a los más recientes.",
              ("region_code", "parcel_id", "min_age_days", "category"), (EXPORT,), b.build_r03),
    ReportDef("R-04", "Alertas emitidas", "operacional",
              "Alertas de riesgo combinadas (clima y diagnósticos) y su estado de envío.",
              ("date_from", "date_to", "alert_level", "region_code", "alert_status"), (EXPORT,), b.build_r04,
              uses_model=False, available_from_phase=5),
    ReportDef("R-05", "Actividad de usuarios", "operacional",
              "Eventos de la bitácora por usuario y módulo: sesiones, acciones y accesos denegados.",
              ("user_email", "role_code", "module_code", "date_from", "date_to"), (EXPORT, AUDIT_VIEW), b.build_r05,
              uses_model=False),
    ReportDef("R-06", "Incidencia por región y variedad", "gestion",
              "Distribución de las categorías de diagnóstico por región, por variedad y cruzada.",
              ("date_from", "date_to", "region_code", "variety_id"), (EXPORT,), b.build_r06),
    ReportDef("R-07", "Tendencias temporales", "gestion",
              "Evolución diaria, semanal o mensual de los diagnósticos por categoría.",
              ("date_from", "date_to", "region_code", "parcel_id", "variety_id", "aggregation"), (EXPORT,),
              b.build_r07),
    ReportDef("R-08", "Desempeño y deriva de los modelos", "gestion",
              "Confianza, tasa de revisión y acuerdo con los expertos por versión de modelo y en el tiempo.",
              ("model_version_id", "date_from", "date_to", "window"), (EXPORT,), b.build_r08),
    ReportDef("R-09", "Tiempos de respuesta", "gestion",
              "Tiempo de inferencia por modelo y tiempo hasta la revisión experta.",
              ("date_from", "date_to", "region_code"), (EXPORT,), b.build_r09),
    ReportDef("R-10", "Uso del sistema", "gestion",
              "Sesiones por rol, permanencia por módulo y actividad diaria (desde la bitácora).",
              ("date_from", "date_to", "role_code"), (EXPORT, AUDIT_VIEW), b.build_r10, uses_model=False),
    ReportDef("B-01", "Bitácora de auditoría", "auditoria",
              "Exportación de los registros de la bitácora con la verificación de la cadena de hash.",
              ("user_email", "module_code", "event_type", "result", "date_from", "date_to"),
              ("bitacora:exportar",), b.build_b01, uses_model=False),
]}

FORMATS = {
    "pdf": ("application/pdf", "pdf"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
}
XLSX_ROW_LIMIT = 50_000


def allowed(defn: ReportDef, permissions: set[str]) -> bool:
    return all(p in permissions for p in defn.permissions)
