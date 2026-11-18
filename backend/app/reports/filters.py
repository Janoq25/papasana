"""Filtros parametrizables de los reportes: validación estricta y descripción para el formulario del frontend."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.labels import CATEGORY_LABELS

MAX_RANGE_DAYS = 3 * 366

STATUS_LABELS = {
    "automatico": "Automático",
    "pendiente_revision": "Pendiente de revisión",
    "validado": "Validado",
    "corregido": "Corregido",
    "anulado": "Anulado",
}
PROVENANCE_LABELS = {"web": "Web", "movil": "Móvil", "n8n": "n8n", "semilla": "Datos de ejemplo"}
GPS_LABELS = {"exif": "EXIF de la foto", "dispositivo": "Ubicación del dispositivo", "manual": "Manual",
              "ninguno": "Sin ubicación"}
AGGREGATION_LABELS = {"dia": "Diaria", "semana": "Semanal", "mes": "Mensual"}
WINDOW_LABELS = {"semana": "Semanal", "mes": "Mensual"}
RESULT_LABELS = {"exito": "Éxito", "fallo": "Fallo"}
ALERT_LEVEL_LABELS = {"alto": "Alto", "medio": "Medio", "bajo": "Bajo"}
ALERT_STATUS_LABELS = {"activa": "Activa", "enviada": "Enviada", "cerrada": "Cerrada"}
EVENT_LABELS = {
    "login": "Inicio de sesión",
    "login_fallido": "Inicio de sesión fallido",
    "bloqueo_cuenta": "Bloqueo de cuenta",
    "logout": "Cierre de sesión",
    "sesion_expirada": "Sesión expirada",
    "modulo_entrada": "Entrada a módulo",
    "modulo_salida": "Salida de módulo",
    "accion": "Acción",
    "acceso_denegado": "Acceso denegado",
}


class ReportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    parcel_id: int | None = Field(default=None, ge=1)
    variety_id: int | None = Field(default=None, ge=1)
    technician_id: uuid.UUID | None = None
    category: Literal["sano", "sospechoso", "tizon_tardio_compatible"] | None = None
    status: Literal["automatico", "pendiente_revision", "validado", "corregido", "anulado"] | None = None
    batch_id: uuid.UUID | None = None
    provenance: Literal["web", "movil", "n8n", "semilla"] | None = None
    min_age_days: int | None = Field(default=None, ge=0, le=3650)
    aggregation: Literal["dia", "semana", "mes"] | None = None
    model_version_id: int | None = Field(default=None, ge=1)
    window: Literal["semana", "mes"] | None = None
    role_code: str | None = Field(default=None, max_length=40)
    user_email: str | None = Field(default=None, max_length=254)
    module_code: str | None = Field(default=None, max_length=40)
    event_type: str | None = Field(default=None, max_length=30)
    result: Literal["exito", "fallo"] | None = None
    alert_level: Literal["alto", "medio", "bajo"] | None = None
    alert_status: Literal["activa", "enviada", "cerrada"] | None = None

    @model_validator(mode="after")
    def _check_dates(self):
        if self.date_from and self.date_to:
            if self.date_from > self.date_to:
                raise ValueError("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")
            if (self.date_to - self.date_from).days > MAX_RANGE_DAYS:
                raise ValueError("El rango de fechas no puede superar 3 años.")
        for name in ("user_email", "role_code", "module_code", "event_type"):
            v = getattr(self, name)
            if isinstance(v, str):
                setattr(self, name, v.strip() or None)
        return self

    def used(self) -> dict:
        """Solo los filtros con valor (para guardar en el historial)."""
        return self.model_dump(mode="json", exclude_none=True)


# Descripción de cada filtro para construir el formulario en el frontend.
# type: date | number | text | select | region | parcel | variety | technician | model | role | module
FILTER_FIELDS: dict[str, dict] = {
    "date_from": {"label": "Desde", "type": "date"},
    "date_to": {"label": "Hasta", "type": "date"},
    "region_code": {"label": "Región", "type": "region"},
    "parcel_id": {"label": "Parcela", "type": "parcel"},
    "variety_id": {"label": "Variedad", "type": "variety"},
    "technician_id": {"label": "Técnico", "type": "technician"},
    "category": {"label": "Categoría", "type": "select", "options": CATEGORY_LABELS},
    "status": {"label": "Estado", "type": "select", "options": STATUS_LABELS},
    "batch_id": {"label": "Lote (ID)", "type": "text"},
    "provenance": {"label": "Procedencia", "type": "select", "options": PROVENANCE_LABELS},
    "min_age_days": {"label": "Antigüedad mínima (días)", "type": "number"},
    "aggregation": {"label": "Agregación", "type": "select", "options": AGGREGATION_LABELS},
    "model_version_id": {"label": "Versión de modelo", "type": "model"},
    "window": {"label": "Ventana", "type": "select", "options": WINDOW_LABELS},
    "role_code": {"label": "Rol", "type": "role"},
    "user_email": {"label": "Usuario (correo)", "type": "text"},
    "module_code": {"label": "Módulo", "type": "module"},
    "event_type": {"label": "Evento", "type": "select", "options": EVENT_LABELS},
    "result": {"label": "Resultado", "type": "select", "options": RESULT_LABELS},
    "alert_level": {"label": "Nivel", "type": "select", "options": ALERT_LEVEL_LABELS},
    "alert_status": {"label": "Estado de la alerta", "type": "select", "options": ALERT_STATUS_LABELS},
}
