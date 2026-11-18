from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_permission
from app.db.session import get_db
from app.schemas.settings import SettingOut, SettingUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["Configuración del sistema"])


@router.get("", response_model=list[SettingOut], summary="Listar parámetros del sistema")
def list_settings(_: CurrentUser = Depends(require_permission("configuracion", "ver")),
                  db: Session = Depends(get_db)):
    return SettingsService(db).list_all()


@router.put("/{key}", response_model=SettingOut, summary="Actualizar un parámetro")
def update_setting(body: SettingUpdate, key: str = Path(max_length=80),
                   current: CurrentUser = Depends(require_permission("configuracion", "editar")),
                   db: Session = Depends(get_db)):
    return SettingsService(db).update(key, body.value, current.user, current.session.id)
