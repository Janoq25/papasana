import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, FetchedValue, Identity, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Tipos de evento de la bitácora
EVENT_TYPES = (
    "login",
    "login_fallido",
    "bloqueo_cuenta",
    "logout",
    "sesion_expirada",
    "modulo_entrada",
    "modulo_salida",
    "accion",
    "acceso_denegado",
)


class AuditLog(Base):
    """Bitácora append-only.

    `seq`, `prev_hash` y `hash` los asigna el trigger `auditoria.trg_audit_chain` (BEFORE INSERT).
    Otro trigger impide UPDATE, DELETE y TRUNCATE.
    """

    __tablename__ = "audit_log"
    __table_args__ = {"schema": "auditoria"}

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    seq: Mapped[int | None] = mapped_column(BigInteger, FetchedValue(), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    user_email: Mapped[str | None] = mapped_column(String(254))
    role_code: Mapped[str | None] = mapped_column(String(40))
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    module_code: Mapped[str | None] = mapped_column(String(40), index=True)
    action: Mapped[str | None] = mapped_column(String(60))
    http_method: Mapped[str | None] = mapped_column(String(10))
    endpoint: Mapped[str | None] = mapped_column(String(255))
    entity_type: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str] = mapped_column(String(10), default="exito")
    error_detail: Mapped[str | None] = mapped_column(Text)
    related_event_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    prev_hash: Mapped[str | None] = mapped_column(String(64), FetchedValue())
    hash: Mapped[str | None] = mapped_column(String(64), FetchedValue())
