import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user, require_permission
from app.core.errors import BusinessRuleError
from app.db.session import get_db
from app.schemas.audit import AuditOut, ModuleEventIn, ModuleEventOut, ModuleTimeOut, VerifyOut
from app.schemas.common import Page
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/audit", tags=["Bitácora de auditoría"])


def _record(db: Session, user, session_id: uuid.UUID, body: ModuleEventIn) -> ModuleEventOut:
    svc = AuditService(db)
    if body.event == "entrada":
        ev = svc.module_enter(user, session_id, body.module_code)
    else:
        if body.entry_event_id is None:
            raise BusinessRuleError("La salida requiere entry_event_id.")
        ev = svc.module_exit(user, session_id, body.entry_event_id, body.reason)
    db.commit()
    return ModuleEventOut(event_id=ev.id, occurred_at=ev.occurred_at, duration_ms=ev.duration_ms)


@router.post("/module-events", response_model=ModuleEventOut, summary="Registrar entrada o salida de módulo")
def module_event(body: ModuleEventIn, current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    return _record(db, current.user, current.session.id, body)


@router.post("/beacon", status_code=status.HTTP_204_NO_CONTENT,
             summary="Salida de módulo vía navigator.sendBeacon (autenticada con la cookie de sesión)")
async def module_beacon(request: Request, db: Session = Depends(get_db),
                        ps_refresh: str | None = Cookie(default=None)):
    # sendBeacon no permite cabecera Authorization: se identifica la sesión con la cookie httpOnly.
    raw = await request.body()
    if len(raw) > 2048:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    session = AuthService(db).session_from_refresh_cookie(ps_refresh)
    if session is not None:
        try:
            body = ModuleEventIn.model_validate(json.loads(raw or b"{}"))
            if body.event == "salida":
                _record(db, session.user, session.id, body)
        except (ValueError, ValidationError, BusinessRuleError):
            pass  # el beacon no tiene respuesta útil para el cliente
        except Exception:
            db.rollback()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=Page[AuditOut], summary="Consultar la bitácora")
def search_audit(
    user_id: uuid.UUID | None = None,
    user_email: str | None = Query(default=None, max_length=254),
    module_code: str | None = Query(default=None, max_length=40),
    event_type: str | None = Query(default=None, max_length=30),
    action: str | None = Query(default=None, max_length=60),
    result: str | None = Query(default=None, pattern="^(exito|fallo)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(require_permission("bitacora", "ver")),
    db: Session = Depends(get_db),
):
    items, total = AuditService(db).search(
        user_id=user_id, user_email=user_email, module_code=module_code, event_type=event_type, action=action,
        result=result, date_from=date_from, date_to=date_to, page=page, size=size, ascending=order == "asc",
    )
    return Page[AuditOut](items=[AuditOut.model_validate(i) for i in items], total=total, page=page, size=size)


@router.get("/module-time", response_model=list[ModuleTimeOut], summary="Tiempo de permanencia por módulo")
def module_time(
    user_id: uuid.UUID | None = None,
    user_email: str | None = Query(default=None, max_length=254),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    _: CurrentUser = Depends(require_permission("bitacora", "ver")),
    db: Session = Depends(get_db),
):
    rows = AuditService(db).module_time(user_id=user_id, user_email=user_email, date_from=date_from, date_to=date_to)
    return [ModuleTimeOut(module_code=m, total_ms=t, visitas=c) for m, t, c in rows]


@router.get("/verify", response_model=VerifyOut, summary="Verificar la integridad de la cadena de hash")
def verify_chain(current: CurrentUser = Depends(require_permission("bitacora", "ver")),
                 db: Session = Depends(get_db)):
    svc = AuditService(db)
    out = svc.verify()
    svc.log("accion", user=current.user, session_id=current.session.id, module_code="bitacora",
            action="verificar_cadena", result="exito" if out["ok"] else "fallo",
            after={"ok": out["ok"], "total": out["total_registros"]})
    db.commit()
    return out
