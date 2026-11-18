from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.api.v1.field_serializers import parcel_out
from app.core.errors import PermissionDeniedError
from app.db.session import get_db
from app.schemas.common import Page
from app.schemas.field import (
    AssignableUserOut,
    AssignmentsIn,
    ParcelIn,
    ParcelOut,
    ParcelUpdate,
    ProducerIn,
    ProducerOut,
)
from app.services.parcel_service import ParcelService

router = APIRouter(tags=["Parcelas"])


@router.get("/parcelas", response_model=Page[ParcelOut], summary="Listar parcelas (según el alcance del rol)")
def list_parcels(
    q: str | None = Query(default=None, max_length=100),
    region: str | None = Query(default=None, pattern=r"^\d{6}$"),
    variety_id: int | None = None,
    active: bool | None = True,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    current: CurrentUser = Depends(require_permission("parcelas", "ver")),
    db: Session = Depends(get_db),
):
    items, total = ParcelService(db).search(current.user, q=q, region=region, variety_id=variety_id,
                                            active=active, page=page, size=size)
    return Page[ParcelOut](items=[parcel_out(db, p, with_geometry=False) for p in items], total=total,
                           page=page, size=size)


@router.get("/parcelas/geojson", summary="Parcelas como FeatureCollection GeoJSON (mapa)")
def parcels_geojson(current: CurrentUser = Depends(require_permission("parcelas", "ver")),
                    db: Session = Depends(get_db)):
    return ParcelService(db).geojson(current.user)


@router.get("/parcelas/opciones", summary="Parcelas activas para formularios (id, código, nombre)")
def parcel_options(current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
                   db: Session = Depends(get_db)):
    items, _ = ParcelService(db).search(current.user, q=None, region=None, variety_id=None, active=True,
                                        page=1, size=500)
    return [{"id": p.id, "code": p.code, "name": p.name, "region_code": p.region_code} for p in items]


@router.get("/parcelas/asignables", response_model=list[AssignableUserOut],
            summary="Usuarios que pueden asignarse a una parcela")
def assignable_users(_: CurrentUser = Depends(require_permission("parcelas", "editar")),
                     db: Session = Depends(get_db)):
    return [AssignableUserOut(id=u.id, full_name=u.full_name, role_name=u.role.name)
            for u in ParcelService(db).assignable_users()]


@router.get("/parcelas/{parcel_id}", response_model=ParcelOut, summary="Detalle de parcela con geometría")
def get_parcel(parcel_id: int, current: CurrentUser = Depends(require_permission("parcelas", "ver")),
               db: Session = Depends(get_db)):
    return parcel_out(db, ParcelService(db).get(parcel_id, current.user))


@router.post("/parcelas", response_model=ParcelOut, status_code=201, summary="Registrar parcela")
def create_parcel(body: ParcelIn, current: CurrentUser = Depends(require_permission("parcelas", "crear")),
                  db: Session = Depends(get_db)):
    p = ParcelService(db).create(body.model_dump(), current.user, current.session.id)
    return parcel_out(db, p)


@router.patch("/parcelas/{parcel_id}", response_model=ParcelOut, summary="Editar parcela")
def update_parcel(parcel_id: int, body: ParcelUpdate,
                  current: CurrentUser = Depends(require_permission("parcelas", "editar")),
                  db: Session = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if data.get("is_active") is False and not current.can("parcelas", "eliminar"):
        raise PermissionDeniedError("Desactivar parcelas requiere el permiso parcelas:eliminar.")
    p = ParcelService(db).update(parcel_id, data, current.user, current.session.id)
    return parcel_out(db, p)


@router.put("/parcelas/{parcel_id}/asignaciones", summary="Asignar técnicos a la parcela")
def set_assignments(parcel_id: int, body: AssignmentsIn,
                    current: CurrentUser = Depends(require_permission("parcelas", "editar")),
                    db: Session = Depends(get_db)):
    return {"asignados": ParcelService(db).set_assignments(parcel_id, body.user_ids, current.user,
                                                           current.session.id)}


@router.get("/productores", response_model=list[ProducerOut], summary="Listar productores")
def list_producers(q: str | None = Query(default=None, max_length=100),
                   current: CurrentUser = Depends(require_permission("parcelas", "ver")),
                   db: Session = Depends(get_db)):
    return ParcelService(db).list_producers(current.user, q)


@router.post("/productores", response_model=ProducerOut, status_code=201, summary="Registrar productor")
def create_producer(body: ProducerIn, current: CurrentUser = Depends(require_permission("parcelas", "crear")),
                    db: Session = Depends(get_db)):
    return ParcelService(db).create_producer(body.model_dump(), current.user, current.session.id)
