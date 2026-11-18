import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.audit_sql import VERIFY_QUERY
from app.models import AuditLog


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def get(self, event_id: int) -> AuditLog | None:
        return self.db.get(AuditLog, event_id)

    def search(
        self,
        *,
        user_id: uuid.UUID | None = None,
        user_email: str | None = None,
        module_code: str | None = None,
        event_type: str | None = None,
        action: str | None = None,
        result: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        size: int = 50,
        ascending: bool = False,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if user_email:
            stmt = stmt.where(func.lower(AuditLog.user_email).like(f"%{user_email.strip().lower()}%"))
        if module_code:
            stmt = stmt.where(AuditLog.module_code == module_code)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if result:
            stmt = stmt.where(AuditLog.result == result)
        if date_from:
            stmt = stmt.where(AuditLog.occurred_at >= date_from)
        if date_to:
            stmt = stmt.where(AuditLog.occurred_at < date_to)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = AuditLog.seq.asc() if ascending else AuditLog.seq.desc()
        items = self.db.scalars(stmt.order_by(order).offset((page - 1) * size).limit(size)).all()
        return list(items), total

    def module_time(
        self,
        *,
        user_id: uuid.UUID | None,
        user_email: str | None = None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[tuple[str, int, int]]:
        stmt = select(
            AuditLog.module_code, func.coalesce(func.sum(AuditLog.duration_ms), 0), func.count()
        ).where(AuditLog.event_type == "modulo_salida")
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if user_email:
            stmt = stmt.where(func.lower(AuditLog.user_email) == user_email.strip().lower())
        if date_from:
            stmt = stmt.where(AuditLog.occurred_at >= date_from)
        if date_to:
            stmt = stmt.where(AuditLog.occurred_at < date_to)
        stmt = stmt.group_by(AuditLog.module_code).order_by(func.sum(AuditLog.duration_ms).desc())
        return [(m or "", int(t), int(c)) for m, t, c in self.db.execute(stmt).all()]

    def find_exit_for(self, entry_id: int) -> AuditLog | None:
        return self.db.scalar(
            select(AuditLog).where(
                AuditLog.event_type == "modulo_salida", AuditLog.related_event_id == entry_id
            )
        )

    def verify_chain(self) -> tuple[int, dict | None, dict | None]:
        total = self.db.scalar(select(func.count()).select_from(AuditLog)) or 0
        broken = self.db.execute(text(VERIFY_QUERY)).mappings().first()
        last = self.db.execute(
            select(AuditLog.seq, AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1)
        ).first()
        return (
            total,
            dict(broken) if broken else None,
            {"seq": last[0], "hash": last[1]} if last else None,
        )
