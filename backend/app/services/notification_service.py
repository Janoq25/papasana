"""Notificaciones internas (módulo A4).

Cada usuario solo ve y marca sus propias notificaciones. Se generan:
- al terminar (o fallar) un reporte solicitado por el usuario;
- cuando un diagnóstico queda pendiente de revisión, para los especialistas cuyo alcance incluye la parcela
  (en los lotes se envía una sola notificación al cerrar el lote, para no saturar la bandeja);
- en la Fase 5, al emitirse alertas de riesgo.
"""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models import Notification, Parcel, ParcelAssignment, User

REVIEW_PERMISSION = "validacion:aprobar"


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    # --- Emisión -----------------------------------------------------------------------------

    def notify(self, user_id: uuid.UUID, kind: str, title: str, body: str | None = None, link: str | None = None,
               entity_type: str | None = None, entity_id=None) -> Notification:
        n = Notification(user_id=user_id, kind=kind, title=title[:160], body=body, link=link,
                         entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None)
        self.db.add(n)
        self.db.flush()
        return n

    def reviewers_for(self, parcel: Parcel, exclude: uuid.UUID | None = None) -> list[User]:
        """Especialistas activos con permiso de validar cuyo alcance de datos incluye la parcela."""
        users = self.db.scalars(select(User).where(User.is_active.is_(True))).unique().all()
        assigned = None
        out = []
        for u in users:
            if u.id == exclude or REVIEW_PERMISSION not in u.role.permission_keys:
                continue
            scope = u.role.data_scope
            if scope == "todo":
                out.append(u)
            elif scope == "region":
                if u.region_code and parcel.region_code[:2] == u.region_code[:2]:
                    out.append(u)
            else:
                if assigned is None:
                    assigned = set(self.db.scalars(select(ParcelAssignment.user_id)
                                                   .where(ParcelAssignment.parcel_id == parcel.id)).all())
                if u.id in assigned or parcel.created_by == u.id:
                    out.append(u)
        return out

    def notify_pending_review(self, parcel: Parcel, *, count: int, uploader: uuid.UUID | None,
                              entity_type: str, entity_id) -> int:
        if count <= 0:
            return 0
        title = ("Nuevo caso pendiente de validación" if count == 1
                 else f"{count} casos nuevos pendientes de validación")
        body = f"Parcela {parcel.code} · {parcel.name}"
        reviewers = self.reviewers_for(parcel, exclude=uploader)
        for r in reviewers:
            self.notify(r.id, "revision_pendiente", title, body, "/validacion", entity_type, entity_id)
        return len(reviewers)

    # --- Consulta (solo las propias) -----------------------------------------------------------

    def list_for(self, user: User, *, unread_only: bool = False, page: int = 1, size: int = 20):
        stmt = select(Notification).where(Notification.user_id == user.id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
                                .offset((page - 1) * size).limit(size)).all()
        return list(items), total

    def unread_count(self, user: User) -> int:
        return self.db.scalar(select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None))) or 0

    def mark_read(self, user: User, notification_id: int) -> bool:
        res = self.db.execute(update(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id, Notification.read_at.is_(None)
        ).values(read_at=now_utc()))
        self.db.commit()
        return bool(res.rowcount)

    def mark_all_read(self, user: User) -> int:
        res = self.db.execute(update(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=now_utc()))
        self.db.commit()
        return res.rowcount or 0
