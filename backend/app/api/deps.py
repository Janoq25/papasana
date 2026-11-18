"""Dependencias de FastAPI: usuario actual, permisos (RBAC) y servicios compartidos."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AuthError, PermissionDeniedError
from app.core.security import decode_access_token, now_utc
from app.db.session import get_db
from app.models import User, UserSession
from app.repositories.security_repo import SessionRepository
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

_bearer = HTTPBearer(auto_error=False, description="Token de acceso JWT")
_TOUCH_EVERY = timedelta(seconds=60)


@dataclass
class CurrentUser:
    user: User
    session: UserSession
    permissions: set[str]

    def can(self, module: str, action: str) -> bool:
        return f"{module}:{action}" in self.permissions


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    x_background: str | None = Header(default=None, alias="X-Background", include_in_schema=False),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthError("Se requiere autenticación.")
    try:
        payload = decode_access_token(creds.credentials)
        session_id = uuid.UUID(payload["sid"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise AuthError("Token inválido o expirado.", code="token_invalido") from e

    session = SessionRepository(db).get(session_id)
    now = now_utc()
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        raise AuthError("La sesión ha finalizado.", code="sesion_finalizada")
    user = session.user
    if not user.is_active or str(user.id) != payload["sub"]:
        raise AuthError("La sesión ha finalizado.", code="sesion_finalizada")
    if AuthService(db).expire_if_idle(session):
        raise AuthError("La sesión expiró por inactividad.", code="sesion_expirada")
    # Las consultas periódicas del frontend (X-Background: 1) no cuentan como actividad del usuario:
    # si contaran, la sesión nunca expiraría por inactividad (docs/decisiones.md D-46).
    if x_background != "1" and now - session.last_seen_at > _TOUCH_EVERY:
        session.last_seen_at = now
        db.commit()
    return CurrentUser(user=user, session=session, permissions=user.role.permission_keys)


def require_permission(module: str, action: str):
    """Dependencia que valida `módulo:acción`; si falla, registra el intento en la bitácora."""

    def _dep(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> CurrentUser:
        if not current.can(module, action):
            AuditService(db).log(
                "acceso_denegado", user=current.user, session_id=current.session.id, module_code=module,
                action=action, result="fallo", error_detail=f"sin permiso {module}:{action}",
            )
            db.commit()
            raise PermissionDeniedError("No tiene permiso para realizar esta acción.",
                                        detail={"requerido": f"{module}:{action}"})
        return current

    return _dep


def require_any_permission(*pairs: tuple[str, str]):
    """Como `require_permission`, pero basta con uno de los permisos `(módulo, acción)` indicados."""

    def _dep(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> CurrentUser:
        if not any(current.can(m, a) for m, a in pairs):
            wanted = " o ".join(f"{m}:{a}" for m, a in pairs)
            AuditService(db).log(
                "acceso_denegado", user=current.user, session_id=current.session.id, module_code=pairs[0][0],
                action=pairs[0][1], result="fallo", error_detail=f"sin permiso {wanted}",
            )
            db.commit()
            raise PermissionDeniedError("No tiene permiso para realizar esta acción.", detail={"requerido": wanted})
        return current

    return _dep
