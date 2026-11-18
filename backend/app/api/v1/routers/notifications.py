from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import Notification
from app.schemas.reports import NotificationOut, NotificationPage, NotificationSummary
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notificaciones", tags=["Notificaciones"])


@router.get("", response_model=NotificationPage, summary="Mis notificaciones")
def list_notifications(unread_only: bool = False, page: int = Query(default=1, ge=1),
                       size: int = Query(default=20, ge=1, le=100),
                       current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = NotificationService(db)
    items, total = svc.list_for(current.user, unread_only=unread_only, page=page, size=size)
    return NotificationPage(items=[NotificationOut.model_validate(n) for n in items], total=total, page=page,
                            size=size, unread=svc.unread_count(current.user))


@router.get("/resumen", response_model=NotificationSummary, summary="No leídas y las 5 más recientes (campana)")
def summary(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    svc = NotificationService(db)
    items, _ = svc.list_for(current.user, page=1, size=5)
    return NotificationSummary(unread=svc.unread_count(current.user),
                               recent=[NotificationOut.model_validate(n) for n in items])


@router.post("/{notification_id}/leida", status_code=status.HTTP_204_NO_CONTENT, summary="Marcar como leída")
def mark_read(notification_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != current.user.id:
        raise NotFoundError("Notificación no encontrada.")
    NotificationService(db).mark_read(current.user, notification_id)  # idempotente si ya estaba leída
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/leer-todas", summary="Marcar todas como leídas")
def mark_all(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"marcadas": NotificationService(db).mark_all_read(current.user)}
