import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class AuditOut(ORMModel):
    id: int
    seq: int | None
    occurred_at: datetime
    user_id: uuid.UUID | None
    user_email: str | None
    role_code: str | None
    session_id: uuid.UUID | None
    event_type: str
    module_code: str | None
    action: str | None
    http_method: str | None
    endpoint: str | None
    entity_type: str | None
    entity_id: str | None
    before: Any | None
    after: Any | None
    ip: str | None
    user_agent: str | None
    result: str
    error_detail: str | None
    related_event_id: int | None
    duration_ms: int | None
    hash: str | None

    @field_validator("ip", mode="before")
    @classmethod
    def _ip_to_str(cls, v):
        return str(v) if v is not None else None


class ModuleEventIn(BaseModel):
    module_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z_]+$")
    event: Literal["entrada", "salida"]
    entry_event_id: int | None = None
    reason: Literal["navegacion", "pestana_oculta", "cierre", "logout", "inactividad"] | None = None


class ModuleEventOut(BaseModel):
    event_id: int
    occurred_at: datetime
    duration_ms: int | None = None


class ModuleTimeOut(BaseModel):
    module_code: str
    total_ms: int
    visitas: int


class VerifyOut(BaseModel):
    ok: bool
    total_registros: int
    primer_registro_alterado: dict | None
    ultimo: dict | None
    verificado_en: datetime
