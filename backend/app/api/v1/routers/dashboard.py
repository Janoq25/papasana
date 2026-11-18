from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.core.errors import BusinessRuleError, NotFoundError
from app.db.session import get_db
from app.services.analytics import FieldFilters, scoped_filter_options
from app.services.dashboard_service import DashboardService
from app.services.scope import can_access_parcel

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", summary="KPIs, tendencia, distribución y mapa de calor (según el alcance del rol)")
def dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    region_code: str | None = Query(default=None, pattern=r"^\d{6}$"),
    parcel_id: int | None = Query(default=None, ge=1),
    variety_id: int | None = Query(default=None, ge=1),
    current: CurrentUser = Depends(require_permission("dashboard", "ver")),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise BusinessRuleError("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")
    if date_from and date_to and (date_to - date_from).days > 3 * 366:
        raise BusinessRuleError("El rango de fechas no puede superar 3 años.")
    if parcel_id and not can_access_parcel(db, current.user, parcel_id):
        raise NotFoundError("Parcela no encontrada o fuera de su alcance.")
    filters = FieldFilters(date_from, date_to, region_code, parcel_id, variety_id)
    return DashboardService(db).build(current.user, filters)


@router.get("/opciones", summary="Regiones, parcelas y variedades para los filtros globales (según el alcance)")
def filter_options(current: CurrentUser = Depends(require_permission("dashboard", "ver")),
                   db: Session = Depends(get_db)):
    return scoped_filter_options(db, current.user)
