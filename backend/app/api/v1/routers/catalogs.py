from fastapi import APIRouter, Depends, File, Path, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.core.errors import BusinessRuleError
from app.db.session import get_db
from app.schemas.field import CatalogItemOut, DiseaseIn, StageIn, VarietyIn
from app.schemas.user import UbigeoOut
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/catalogos", tags=["Catálogos"])

_SCHEMAS = {"variedades": VarietyIn, "estadios": StageIn, "enfermedades": DiseaseIn}
_CATALOG_PATTERN = "^(variedades|estadios|enfermedades)$"


@router.get("/ubigeo", response_model=list[UbigeoOut], summary="Regiones (ubigeo INEI)")
def list_ubigeo(level: str = Query(default="departamento", pattern="^(departamento|provincia|distrito)$"),
                parent: str | None = Query(default=None, pattern=r"^\d{6}$"),
                q: str | None = Query(default=None, max_length=60),
                _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return CatalogService(db).list_ubigeo(level, parent, q)


@router.post("/ubigeo/importar", summary="Importar provincias y distritos desde CSV (columnas ubigeo, nombre)")
async def import_ubigeo(file: UploadFile = File(...),
                        current: CurrentUser = Depends(require_permission("catalogos", "crear")),
                        db: Session = Depends(get_db)):
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise BusinessRuleError("El archivo no debe superar 5 MB.")
    return CatalogService(db).import_ubigeo(raw, current.user, current.session.id)


@router.get("/{catalog}", response_model=list[CatalogItemOut], summary="Listar un catálogo")
def list_catalog(catalog: str = Path(pattern=_CATALOG_PATTERN), include_inactive: bool = False,
                 _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    # Los catálogos se usan en formularios de varios módulos: basta con estar autenticado para leerlos.
    return CatalogService(db).list_items(catalog, include_inactive)


@router.post("/{catalog}", response_model=CatalogItemOut, status_code=201, summary="Crear elemento")
def create_item(body: dict, catalog: str = Path(pattern=_CATALOG_PATTERN),
                current: CurrentUser = Depends(require_permission("catalogos", "crear")),
                db: Session = Depends(get_db)):
    data = _SCHEMAS[catalog].model_validate(body).model_dump()
    return CatalogService(db).create(catalog, data, current.user, current.session.id)


@router.patch("/{catalog}/{item_id}", response_model=CatalogItemOut, summary="Editar elemento")
def update_item(item_id: int, body: dict, catalog: str = Path(pattern=_CATALOG_PATTERN),
                current: CurrentUser = Depends(require_permission("catalogos", "editar")),
                db: Session = Depends(get_db)):
    schema = _SCHEMAS[catalog]
    partial = {k: v for k, v in body.items() if k in schema.model_fields}
    data = schema.model_validate({**_defaults_for(catalog), **partial}).model_dump(include=set(partial))
    return CatalogService(db).update(catalog, item_id, data, current.user, current.session.id)


@router.delete("/{catalog}/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Desactivar elemento")
def deactivate_item(item_id: int, catalog: str = Path(pattern=_CATALOG_PATTERN),
                    current: CurrentUser = Depends(require_permission("catalogos", "eliminar")),
                    db: Session = Depends(get_db)):
    CatalogService(db).deactivate(catalog, item_id, current.user, current.session.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _defaults_for(catalog: str) -> dict:
    # Valores de relleno para validar actualizaciones parciales con el mismo esquema
    return {"variedades": {"name": "xx"}, "estadios": {"name": "xx", "code": "xx"},
            "enfermedades": {"name": "xx"}}[catalog]
