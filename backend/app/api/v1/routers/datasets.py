from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.lab import DatasetIn, DatasetOut, DatasetUpdate, LicenseIn
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["Datasets y licencias"])


def _out(db: Session, d) -> DatasetOut:
    out = DatasetOut.model_validate(d)
    if d.license_verified_by:
        out.license_verified_by_name = db.scalar(select(User.full_name).where(User.id == d.license_verified_by))
    out.usable = d.license_status == "verificada" and d.is_active
    return out


@router.get("", response_model=list[DatasetOut], summary="Registro de datasets con el estado de su licencia")
def list_datasets(_: CurrentUser = Depends(require_permission("datasets", "ver")), db: Session = Depends(get_db)):
    return [_out(db, d) for d in DatasetService(db).list_all()]


@router.get("/exportar", summary="Exportar el registro como ml/datasets.yaml", response_class=Response)
def export(current: CurrentUser = Depends(require_permission("datasets", "exportar")), db: Session = Depends(get_db)):
    text = DatasetService(db).export_yaml(current.user, current.session.id)
    return Response(text, media_type="application/x-yaml",
                    headers={"Content-Disposition": 'attachment; filename="datasets.yaml"'})


@router.post("", response_model=DatasetOut, status_code=201, summary="Registrar un dataset (licencia por verificar)")
def create(body: DatasetIn, current: CurrentUser = Depends(require_permission("datasets", "crear")),
           db: Session = Depends(get_db)):
    return _out(db, DatasetService(db).create(body.model_dump(mode="json"), current.user, current.session.id))


@router.patch("/{dataset_id}", response_model=DatasetOut, summary="Editar datos descriptivos")
def update(dataset_id: int, body: DatasetUpdate,
           current: CurrentUser = Depends(require_permission("datasets", "editar")), db: Session = Depends(get_db)):
    data = body.model_dump(mode="json", exclude_unset=True)
    return _out(db, DatasetService(db).update(dataset_id, data, current.user, current.session.id))


@router.put("/{dataset_id}/licencia", response_model=DatasetOut,
            summary="Registrar la verificación (o el rechazo) de la licencia en la fuente oficial")
def set_license(dataset_id: int, body: LicenseIn,
                current: CurrentUser = Depends(require_permission("datasets", "editar")),
                db: Session = Depends(get_db)):
    return _out(db, DatasetService(db).set_license(dataset_id, body.model_dump(mode="json"), current.user,
                                                   current.session.id))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar (si ningún modelo lo usa)")
def delete(dataset_id: int, current: CurrentUser = Depends(require_permission("datasets", "eliminar")),
           db: Session = Depends(get_db)):
    DatasetService(db).delete(dataset_id, current.user, current.session.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
