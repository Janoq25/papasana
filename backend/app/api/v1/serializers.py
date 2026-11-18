"""Conversión de modelos a esquemas de salida que requieren datos adicionales."""

from sqlalchemy.orm import Session

from app.models import Role, User
from app.schemas.role import RoleOut
from app.schemas.user import MeOut
from app.services.settings_service import SettingsService


def me_out(db: Session, user: User) -> MeOut:
    settings = SettingsService(db)
    out = MeOut.model_validate(user)
    out.permissions = sorted(user.role.permission_keys)
    out.session_settings = {
        "minutos_inactividad": settings.get("seguridad.minutos_inactividad"),
        "longitud_minima_contrasena": settings.get("seguridad.longitud_minima_contrasena"),
        "institucion": settings.get("institucion.nombre"),
        "aviso": settings.get("aviso.supervision_profesional"),
    }
    return out


def role_out(role: Role, user_count: int) -> RoleOut:
    return RoleOut(
        id=role.id, code=role.code, name=role.name, description=role.description,
        data_scope=role.data_scope, is_system=role.is_system, user_count=user_count,
        permissions=sorted(role.permission_keys),
    )
