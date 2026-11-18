"""Registro y consulta de la bitácora de auditoría."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.context import get_request_context
from app.core.errors import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models import AuditLog, User
from app.repositories.audit_repo import AuditRepository
from app.repositories.security_repo import RoleRepository

# Campos que nunca deben quedar en before/after
_SENSITIVE = {"password", "password_hash", "refresh_token_hash", "previous_token_hash", "token_hash",
              "api_key_hash", "new_password", "current_password"}

EXIT_REASONS = {"navegacion", "pestana_oculta", "cierre", "logout", "inactividad"}


def snapshot(obj: Any, fields: list[str] | None = None) -> dict | None:
    """Convierte un objeto o dict en JSON serializable, omitiendo campos sensibles."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        data = dict(obj)
    else:
        names = fields or [c.key for c in obj.__table__.columns]
        data = {n: getattr(obj, n) for n in names}
    clean = {k: v for k, v in data.items() if k not in _SENSITIVE}
    return jsonable_encoder(clean)


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditRepository(db)

    def log(
        self,
        event_type: str,
        *,
        user: User | None = None,
        user_id: uuid.UUID | None = None,
        user_email: str | None = None,
        role_code: str | None = None,
        session_id: uuid.UUID | None = None,
        module_code: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: Any = None,
        before: dict | None = None,
        after: dict | None = None,
        result: str = "exito",
        error_detail: str | None = None,
        related_event_id: int | None = None,
        duration_ms: int | None = None,
    ) -> AuditLog:
        ctx = get_request_context()
        entry = AuditLog(
            event_type=event_type,
            user_id=user.id if user else user_id,
            user_email=user.email if user else user_email,
            role_code=(user.role.code if user and user.role else role_code),
            session_id=session_id,
            module_code=module_code,
            action=action,
            http_method=ctx.method,
            endpoint=ctx.endpoint,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            ip=ctx.ip,
            user_agent=(ctx.user_agent or "")[:500] or None,
            result=result,
            error_detail=error_detail,
            related_event_id=related_event_id,
            duration_ms=duration_ms,
        )
        return self.repo.add(entry)

    # --- Entrada / salida de módulos --------------------------------------------------------

    def module_enter(self, user: User, session_id: uuid.UUID, module_code: str) -> AuditLog:
        self._check_module(module_code)
        return self.log("modulo_entrada", user=user, session_id=session_id, module_code=module_code,
                        action="entrar")

    def module_exit(
        self, user: User, session_id: uuid.UUID, entry_event_id: int, reason: str | None
    ) -> AuditLog:
        entry = self.repo.get(entry_event_id)
        if entry is None or entry.event_type != "modulo_entrada":
            raise NotFoundError("Evento de entrada no encontrado.")
        if entry.user_id != user.id or entry.session_id != session_id:
            raise PermissionDeniedError("El evento de entrada pertenece a otra sesión.")
        existing = self.repo.find_exit_for(entry_event_id)
        if existing is not None:
            return existing  # idempotente: beacon y fetch pueden llegar ambos
        reason = reason if reason in EXIT_REASONS else "navegacion"
        duration = int((datetime.now(UTC) - entry.occurred_at).total_seconds() * 1000)
        return self.log(
            "modulo_salida",
            user=user,
            session_id=session_id,
            module_code=entry.module_code,
            action="salir",
            related_event_id=entry.id,
            duration_ms=max(duration, 0),
            after={"motivo": reason, "entrada_en": entry.occurred_at.isoformat()},
        )

    def _check_module(self, module_code: str) -> None:
        if module_code not in RoleRepository(self.db).module_codes():
            raise BusinessRuleError(f"Módulo desconocido: {module_code}")

    # --- Consultas ------------------------------------------------------------------------

    def search(self, **filters):
        return self.repo.search(**filters)

    def module_time(self, **filters):
        return self.repo.module_time(**filters)

    def verify(self) -> dict:
        total, broken, last = self.repo.verify_chain()
        return {
            "ok": broken is None,
            "total_registros": total,
            "primer_registro_alterado": broken,
            "ultimo": last,
            "verificado_en": datetime.now(UTC),
        }
