"""Reportes (M10): solicitud, generación en segundo plano, historial y descarga.

Flujo: POST /reportes crea un `ReportJob` (pendiente) y lo encola en Celery → el worker arma el documento con
los permisos y el alcance del solicitante, lo renderiza y lo guarda en MinIO → notificación interna →
el usuario lo descarga desde el historial. La solicitud y cada descarga quedan en la bitácora.
"""

import logging
import re
import unicodedata
import uuid

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.core.security import now_utc
from app.core.timeutil import fmt_date, to_local
from app.domain.labels import CATEGORY_LABELS
from app.models import ModelVersion, Module, Parcel, PotatoVariety, ReportJob, Role, Ubigeo, User
from app.reports.builders import BuildContext
from app.reports.definitions import FORMATS, KIND_LABELS, REPORTS, XLSX_ROW_LIMIT, ReportDef, allowed
from app.reports.document import ReportDocument
from app.reports.filters import FILTER_FIELDS, ReportFilters
from app.services.analytics import current_model, scoped_filter_options
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.scope import can_access_parcel
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageService

log = logging.getLogger("papasana")

MAX_ACTIVE_JOBS = 5
STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_ERROR = "pendiente", "procesando", "listo", "error"


def render(doc: ReportDocument, fmt: str) -> bytes:
    if fmt == "pdf":
        from app.reports.render_pdf import render_pdf

        return render_pdf(doc)
    if fmt == "docx":
        from app.reports.render_docx import render_docx

        return render_docx(doc)
    from app.reports.render_xlsx import render_xlsx

    return render_xlsx(doc)


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:50]


def _module_for(defn: ReportDef) -> str:
    return "bitacora" if defn.kind == "auditoria" else "reportes"


class ReportService:
    def __init__(self, db: Session, storage: StorageService):
        self.db = db
        self.storage = storage
        self.settings = SettingsService(db)
        self.audit = AuditService(db)
        self.cfg = get_settings()

    # --- Catálogo y opciones de filtros ------------------------------------------------------------

    def catalog(self, permissions: set[str]) -> list[dict]:
        out = []
        for d in REPORTS.values():
            if not allowed(d, permissions):
                continue
            out.append({
                "code": d.code, "title": d.title, "kind": d.kind, "kind_label": KIND_LABELS[d.kind],
                "description": d.description, "formats": list(FORMATS),
                "filters": [{"key": k, **FILTER_FIELDS[k]} for k in d.filters],
                "available_from_phase": d.available_from_phase,
            })
        return out

    def options(self, user: User) -> dict:
        db = self.db
        techs = []
        for u in db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.full_name)).unique():
            if "diagnostico:crear" not in u.role.permission_keys:
                continue
            s = user.role.data_scope
            same_region = bool(u.region_code and user.region_code and u.region_code[:2] == user.region_code[:2])
            if s == "todo" or u.id == user.id or (s == "region" and same_region):
                techs.append({"id": str(u.id), "name": u.full_name, "email": u.email})

        audit = "bitacora:ver" in user.role.permission_keys or "bitacora:exportar" in user.role.permission_keys
        roles = db.execute(select(Role.code, Role.name).order_by(Role.name)).all() if audit else []
        modules = db.execute(select(Module.code, Module.name).order_by(Module.name)).all() if audit else []
        return {
            **scoped_filter_options(db, user),
            "technicians": techs,
            "model_versions": [{"id": m.id, "name": m.display_name, "stage": m.stage, "is_demo": m.is_demo}
                               for m in db.scalars(select(ModelVersion).order_by(ModelVersion.id.desc())).all()],
            "roles": [{"code": c, "name": n} for c, n in roles],
            "modules": [{"code": c, "name": n} for c, n in modules],
        }

    # --- Solicitud -----------------------------------------------------------------------------------

    def request(self, user: User, session_id, permissions: set[str], code: str, fmt: str, raw_filters: dict,
                source: str = "web") -> ReportJob:
        defn = REPORTS.get(code)
        if defn is None:
            raise NotFoundError(f"Reporte desconocido: {code}")
        if fmt not in FORMATS:
            raise BusinessRuleError("Formato no válido: use pdf, docx o xlsx.")
        if not allowed(defn, permissions):
            self.audit.log("acceso_denegado", user=user, session_id=session_id, module_code=_module_for(defn),
                           action="exportar", result="fallo", entity_type="reporte", entity_id=code,
                           error_detail=f"sin permiso para {code}: {', '.join(defn.permissions)}")
            self.db.commit()
            raise PermissionDeniedError("No tiene permiso para generar este reporte.",
                                        detail={"requerido": list(defn.permissions)})
        try:
            filters = ReportFilters.model_validate(raw_filters or {})
        except ValidationError as e:
            msgs = [err["msg"].removeprefix("Value error, ") for err in e.errors()]
            raise BusinessRuleError("Filtros no válidos.", code="filtros_invalidos", detail=msgs) from e
        used = filters.used()
        extra = sorted(set(used) - set(defn.filters))
        if extra:
            raise BusinessRuleError(f"El reporte {code} no admite los filtros: {', '.join(extra)}.",
                                    code="filtros_invalidos")
        if filters.parcel_id and not can_access_parcel(self.db, user, filters.parcel_id):
            raise NotFoundError("Parcela no encontrada o fuera de su alcance.")
        if filters.technician_id and user.role.data_scope == "propio" and filters.technician_id != user.id:
            raise PermissionDeniedError("Solo puede filtrar por sus propios diagnósticos.")
        active = self.db.scalar(select(func.count()).select_from(ReportJob).where(
            ReportJob.requested_by == user.id, ReportJob.status.in_((STATUS_PENDING, STATUS_RUNNING)))) or 0
        if active >= MAX_ACTIVE_JOBS:
            raise BusinessRuleError(f"Tiene {active} reportes en proceso. Espere a que terminen.",
                                    code="demasiados_reportes")

        job = ReportJob(report_code=code, format=fmt, filters=used, status=STATUS_PENDING, requested_by=user.id,
                        source=source)
        self.db.add(job)
        self.db.flush()
        self.audit.log("accion", user=user, session_id=session_id, module_code=_module_for(defn), action="exportar",
                       entity_type="reporte", entity_id=job.id,
                       after={"reporte": code, "formato": fmt, "filtros": used, "origen": source})
        self.db.commit()
        return job

    def mark_enqueue_failed(self, job: ReportJob) -> None:
        job.status = STATUS_ERROR
        job.error = "No se pudo encolar la generación (servicio de tareas no disponible). Intente nuevamente."
        job.finished_at = now_utc()
        self.db.commit()

    # --- Generación (worker) ------------------------------------------------------------------------------

    def build_document(self, job: ReportJob, user: User) -> ReportDocument:
        defn = REPORTS[job.report_code]
        filters = ReportFilters.model_validate(job.filters or {})
        limit = XLSX_ROW_LIMIT if job.format == "xlsx" else int(self.settings.get("reportes.max_filas"))
        result = defn.builder(BuildContext(self.db, user, filters, limit))
        model = current_model(self.db) if defn.uses_model else None
        model_line = None
        if defn.uses_model:
            model_line = (f"{model.display_name} (etapa: {model.stage})" if model else "Sin modelo registrado")
        return ReportDocument(
            code=defn.code, title=defn.title, kind_label=KIND_LABELS[defn.kind], description=defn.description,
            header=str(self.settings.get("institucion.encabezado_reportes")), issued_at=now_utc(),
            issued_by=f"{user.full_name} ({user.email}) · {user.role.name}",
            filters=self.describe_filters(filters, defn), model_line=model_line,
            is_demo=bool(model and model.is_demo),
            disclaimer=str(self.settings.get("aviso.supervision_profesional")) if defn.uses_model else None,
            summary=result.summary, tables=result.tables, notes=result.notes,
        )

    def run(self, job_id: uuid.UUID) -> ReportJob | None:
        job = self.db.get(ReportJob, job_id)
        if job is None or job.status not in (STATUS_PENDING, STATUS_RUNNING):
            return job  # idempotente ante reintentos
        job.status, job.started_at, job.error = STATUS_RUNNING, now_utc(), None
        self.db.commit()
        defn = REPORTS.get(job.report_code)
        user = self.db.get(User, job.requested_by)
        try:
            if defn is None or user is None or not user.is_active:
                raise BusinessRuleError("El usuario solicitante ya no está activo.")
            if not allowed(defn, user.role.permission_keys):
                raise BusinessRuleError("El usuario ya no tiene permiso para este reporte.")
            doc = self.build_document(job, user)
            data = render(doc, job.format)
            content_type, ext = FORMATS[job.format]
            local = to_local(doc.issued_at)
            key = f"{local:%Y/%m}/{job.id}.{ext}"
            self.storage.put_bytes(self.cfg.bucket_reports, key, data, content_type)
            job.status, job.object_key, job.content_type = STATUS_DONE, key, content_type
            job.file_name = f"{defn.code}_{_slug(defn.title)}_{local:%Y%m%d_%H%M}.{ext}"
            job.size_bytes, job.row_count, job.finished_at = len(data), doc.row_count, now_utc()
            NotificationService(self.db).notify(
                user.id, "reporte_listo", f"Reporte listo: {defn.code} ({job.format.upper()})", defn.title,
                "/bitacora" if defn.kind == "auditoria" else "/reportes", "reporte", job.id)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            job = self.db.get(ReportJob, job_id)
            known = isinstance(e, BusinessRuleError)
            if not known:
                log.exception("Error al generar el reporte %s", job_id)
            job.status, job.finished_at = STATUS_ERROR, now_utc()
            job.error = (e.message if known else "Error interno al generar el reporte.")[:500]
            if user is not None:
                NotificationService(self.db).notify(
                    user.id, "reporte_error", f"No se pudo generar {job.report_code}", job.error,
                    "/reportes", "reporte", job.id)
            self.db.commit()
        return job

    # --- Historial y descarga ------------------------------------------------------------------------------

    def history(self, user: User, *, page: int = 1, size: int = 20, code: str | None = None):
        stmt = select(ReportJob).where(ReportJob.requested_by == user.id)
        if code:
            stmt = stmt.where(ReportJob.report_code == code)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(stmt.order_by(ReportJob.created_at.desc()).offset((page - 1) * size).limit(size)).all()
        return list(items), total

    def get_own(self, job_id: uuid.UUID, user: User) -> ReportJob:
        job = self.db.get(ReportJob, job_id)
        if job is None or job.requested_by != user.id:
            raise NotFoundError("Reporte no encontrado.")
        return job

    def download(self, job_id: uuid.UUID, user: User, session_id, permissions: set[str]) -> tuple[bytes, ReportJob]:
        job = self.get_own(job_id, user)
        defn = REPORTS.get(job.report_code)
        if defn is None or not allowed(defn, permissions):
            raise PermissionDeniedError("Ya no tiene permiso para descargar este reporte.")
        if job.status != STATUS_DONE or not job.object_key:
            raise BusinessRuleError("El reporte todavía no está listo.", code="reporte_no_listo")
        data = self.storage.get_bytes(self.cfg.bucket_reports, job.object_key)
        job.download_count += 1
        job.last_downloaded_at = now_utc()
        self.audit.log("accion", user=user, session_id=session_id, module_code=_module_for(defn), action="descargar",
                       entity_type="reporte", entity_id=job.id,
                       after={"reporte": job.report_code, "formato": job.format, "archivo": job.file_name,
                              "bytes": job.size_bytes})
        self.db.commit()
        return data, job

    # --- Descripción legible de los filtros ---------------------------------------------------------------------

    def describe_filters(self, f: ReportFilters, defn: ReportDef) -> list[tuple[str, str]]:
        db = self.db
        out = []
        for key, value in f.used().items():
            meta = FILTER_FIELDS[key]
            label = meta["label"]
            if key in ("date_from", "date_to"):
                text = fmt_date(getattr(f, key))
            elif meta["type"] == "select":
                text = meta["options"].get(value, value)
            elif key == "region_code":
                text = db.scalar(select(Ubigeo.name).where(Ubigeo.code == value)) or value
            elif key == "parcel_id":
                p = db.get(Parcel, value)
                text = f"{p.code} · {p.name}" if p else str(value)
            elif key == "variety_id":
                text = db.scalar(select(PotatoVariety.name).where(PotatoVariety.id == value)) or str(value)
            elif key == "technician_id":
                u = db.get(User, f.technician_id)
                text = u.full_name if u else str(value)
            elif key == "model_version_id":
                text = db.scalar(select(ModelVersion.display_name).where(ModelVersion.id == value)) or str(value)
            elif key == "role_code":
                text = db.scalar(select(Role.name).where(Role.code == value)) or value
            elif key == "module_code":
                text = db.scalar(select(Module.name).where(Module.code == value)) or value
            elif key == "category":
                text = CATEGORY_LABELS.get(value, value)
            else:
                text = str(value)
            out.append((label, text))
        return out
