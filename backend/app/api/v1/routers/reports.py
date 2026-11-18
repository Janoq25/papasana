import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_any_permission
from app.db.session import get_db
from app.reports.definitions import REPORTS
from app.schemas.common import Page
from app.schemas.reports import ReportJobOut, ReportRequest
from app.services.report_service import ReportService
from app.services.storage_service import StorageService, get_storage
from app.workers.tasks import generate_report

router = APIRouter(prefix="/reportes", tags=["Reportes"])

# El historial y el catálogo los usan tanto el módulo de reportes como la exportación de la bitácora.
_any_reports = require_any_permission(("reportes", "ver"), ("bitacora", "exportar"))


def _out(job) -> ReportJobOut:
    out = ReportJobOut.model_validate(job)
    defn = REPORTS.get(job.report_code)
    out.report_title = defn.title if defn else None
    return out


@router.get("/catalogo", summary="Reportes que el usuario puede generar, con sus filtros")
def catalog(current: CurrentUser = Depends(_any_reports), db: Session = Depends(get_db),
            storage: StorageService = Depends(get_storage)):
    return ReportService(db, storage).catalog(current.permissions)


@router.get("/opciones", summary="Valores disponibles para los filtros (según el alcance del rol)")
def options(current: CurrentUser = Depends(_any_reports), db: Session = Depends(get_db),
            storage: StorageService = Depends(get_storage)):
    return ReportService(db, storage).options(current.user)


@router.get("", response_model=Page[ReportJobOut], summary="Historial de reportes solicitados por el usuario")
def history(code: str | None = Query(default=None, pattern=r"^[RB]-\d{2}$"), page: int = Query(default=1, ge=1),
            size: int = Query(default=20, ge=1, le=100), current: CurrentUser = Depends(_any_reports),
            db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    items, total = ReportService(db, storage).history(current.user, page=page, size=size, code=code)
    return Page[ReportJobOut](items=[_out(j) for j in items], total=total, page=page, size=size)


@router.post("", response_model=ReportJobOut, status_code=status.HTTP_202_ACCEPTED,
             summary="Solicitar un reporte (se genera en segundo plano)")
def request_report(body: ReportRequest, current: CurrentUser = Depends(_any_reports), db: Session = Depends(get_db),
                   storage: StorageService = Depends(get_storage)):
    svc = ReportService(db, storage)
    job = svc.request(current.user, current.session.id, current.permissions, body.code, body.format, body.filters)
    try:
        generate_report.delay(str(job.id))
    except Exception:
        svc.mark_enqueue_failed(job)
    return _out(job)


@router.get("/{job_id}", response_model=ReportJobOut, summary="Estado de un reporte")
def get_report(job_id: uuid.UUID, current: CurrentUser = Depends(_any_reports), db: Session = Depends(get_db),
               storage: StorageService = Depends(get_storage)):
    return _out(ReportService(db, storage).get_own(job_id, current.user))


@router.get("/{job_id}/descarga", response_class=Response, summary="Descargar el archivo generado")
def download(job_id: uuid.UUID, current: CurrentUser = Depends(_any_reports), db: Session = Depends(get_db),
             storage: StorageService = Depends(get_storage)):
    data, job = ReportService(db, storage).download(job_id, current.user, current.session.id, current.permissions)
    name = job.file_name or f"{job.report_code}.{job.format}"
    return Response(content=data, media_type=job.content_type, headers={
        "Content-Disposition": f"attachment; filename=\"{name.encode('ascii', 'ignore').decode()}\"; "
                               f"filename*=UTF-8''{quote(name)}",
        "Cache-Control": "no-store",
    })
