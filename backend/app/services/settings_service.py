"""Configuración del sistema (módulo A2): parámetros editables sin tocar código, con bitácora."""

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError
from app.models import SystemSetting, User
from app.services.audit_service import AuditService


@dataclass(frozen=True)
class SettingSpec:
    type: type
    default: Any
    description: str
    min: float | None = None
    max: float | None = None
    max_length: int | None = None


SPECS: dict[str, SettingSpec] = {
    "seguridad.max_intentos_login": SettingSpec(
        int, 5, "Intentos fallidos de inicio de sesión antes de bloquear la cuenta.", 1, 20),
    "seguridad.minutos_bloqueo": SettingSpec(
        int, 15, "Minutos que permanece bloqueada una cuenta tras superar los intentos.", 1, 1440),
    "seguridad.minutos_inactividad": SettingSpec(
        int, 30, "Minutos de inactividad tras los cuales se cierra la sesión.", 5, 480),
    "seguridad.longitud_minima_contrasena": SettingSpec(
        int, 10, "Longitud mínima de las contraseñas.", 8, 64),
    "diagnostico.umbral_revision": SettingSpec(
        float, 0.70, "Confianza mínima; por debajo, el diagnóstico se marca como 'requiere revisión'.", 0.0, 1.0),
    "diagnostico.distancia_duplicado": SettingSpec(
        int, 6, "Distancia de Hamming máxima (dHash de 64 bits) para marcar una foto como casi duplicada.", 0, 20),
    "diagnostico.max_imagenes_lote": SettingSpec(
        int, 20, "Número máximo de fotografías por carga en lote.", 1, 50),
    "reportes.max_filas": SettingSpec(
        int, 5000, "Filas máximas por tabla en los reportes PDF y Word (Excel admite hasta 50 000).", 100, 20000),
    "dashboard.dias_casos_recientes": SettingSpec(
        int, 14, "Ventana en días del indicador 'parcelas con casos compatibles recientes' del dashboard.", 1, 90),
    "institucion.nombre": SettingSpec(
        str, "PapaSana AP-01 — Prototipo de investigación", "Nombre que aparece en la interfaz.",
        max_length=160),
    "institucion.encabezado_reportes": SettingSpec(
        str, "PapaSana AP-01 · Sistema de apoyo a la decisión para el tizón tardío de la papa",
        "Encabezado institucional de los reportes.", max_length=300),
    "aviso.supervision_profesional": SettingSpec(
        str,
        "Herramienta de apoyo a la decisión. Los resultados no constituyen un diagnóstico definitivo y "
        "deben ser revisados por un profesional agrónomo.",
        "Aviso de supervisión profesional mostrado en diagnósticos, asistente y reportes.", max_length=600),
}

_CACHE_TTL = 30.0
_cache: dict[str, tuple[float, Any]] = {}


def _validate(key: str, value: Any) -> Any:
    spec = SPECS.get(key)
    if spec is None:
        raise NotFoundError(f"Parámetro desconocido: {key}")
    try:
        if spec.type is int:
            if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
                raise ValueError
            value = int(value)
        elif spec.type is float:
            if isinstance(value, bool):
                raise ValueError
            value = float(value)
        elif spec.type is str:
            if not isinstance(value, str):
                raise ValueError
            value = value.strip()
            if not value:
                raise BusinessRuleError("El valor no puede estar vacío.")
    except (TypeError, ValueError) as e:
        raise BusinessRuleError(f"Tipo de valor inválido para {key}.") from e
    if spec.min is not None and value < spec.min:
        raise BusinessRuleError(f"El valor mínimo de {key} es {spec.min}.")
    if spec.max is not None and value > spec.max:
        raise BusinessRuleError(f"El valor máximo de {key} es {spec.max}.")
    if spec.max_length is not None and len(value) > spec.max_length:
        raise BusinessRuleError(f"{key} admite como máximo {spec.max_length} caracteres.")
    return value


class SettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str) -> Any:
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        row = self.db.get(SystemSetting, key)
        value = row.value if row is not None else SPECS[key].default
        _cache[key] = (time.monotonic() + _CACHE_TTL, value)
        return value

    def list_all(self) -> list[dict]:
        rows = {r.key: r for r in self.db.scalars(select(SystemSetting)).all()}
        out = []
        for key, spec in SPECS.items():
            r = rows.get(key)
            out.append({
                "key": key,
                "value": r.value if r else spec.default,
                "description": spec.description,
                "type": spec.type.__name__,
                "min": spec.min,
                "max": spec.max,
                "updated_at": r.updated_at if r else None,
            })
        return out

    def update(self, key: str, value: Any, actor: User, session_id) -> dict:
        new_value = _validate(key, value)
        row = self.db.get(SystemSetting, key)
        old_value = row.value if row else SPECS[key].default
        if row is None:
            row = SystemSetting(key=key, value=new_value, description=SPECS[key].description,
                                updated_by=actor.id)
            self.db.add(row)
        else:
            row.value = new_value
            row.updated_by = actor.id
        self.db.flush()
        AuditService(self.db).log(
            "accion", user=actor, session_id=session_id, module_code="configuracion", action="editar",
            entity_type="parametro", entity_id=key, before={"valor": old_value}, after={"valor": new_value},
        )
        self.db.commit()
        _cache.pop(key, None)
        return next(s for s in self.list_all() if s["key"] == key)


def clear_settings_cache() -> None:
    _cache.clear()
