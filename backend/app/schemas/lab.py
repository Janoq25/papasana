import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import ORMModel


class LabModelOut(ORMModel):
    id: int
    model_key: str
    architecture: str
    display_name: str
    source: str
    stage: str
    is_demo: bool
    smoke_test: bool
    label_scheme: str
    classes: list
    temperature: float
    mlflow_model_name: str | None
    mlflow_version: str | None
    mlflow_run_id: str | None
    train_dataset_ids: list
    metrics_summary: dict | None
    registered_at: datetime | None
    synced_at: datetime | None


class PromotionIn(BaseModel):
    model_version_id: int
    action: Literal["promover", "rollback"]
    reason: str = Field(min_length=10, max_length=2000)


class DecisionIn(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class UserBrief(ORMModel):
    id: uuid.UUID
    full_name: str
    email: str


class PromotionOut(ORMModel):
    id: int
    action: str
    status: str
    from_stage: str | None
    to_stage: str
    model_version: LabModelOut
    previous: LabModelOut | None
    requested_by: uuid.UUID
    requested_by_name: str | None = None
    request_reason: str
    decided_by: uuid.UUID | None
    decided_by_name: str | None = None
    decision_reason: str | None
    error: str | None
    created_at: datetime
    decided_at: datetime | None


# --- Datasets y licencias (A1) ----------------------------------------------------------------------

Conditions = Literal["laboratorio", "campo", "mixto", "sintetico"]
Etiology = Literal["no", "parcial", "si"]


class DatasetBase(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    version: str | None = Field(default=None, max_length=40)
    source_url: HttpUrl | None = None
    citation: str | None = Field(default=None, max_length=4000)
    conditions: Conditions
    etiological_confirmation: Etiology = "no"
    has_group_ids: bool = False
    role: Literal["entrenamiento", "validacion_externa", "validacion_prospectiva", "prueba_de_humo"]
    class_map: dict[str, str] = Field(default_factory=dict)
    n_images: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)


class DatasetIn(DatasetBase):
    code: str = Field(pattern=r"^[a-z0-9_]{3,60}$")
    license: str | None = Field(default=None, max_length=200)
    license_url: HttpUrl | None = None
    license_notes: str | None = Field(default=None, max_length=4000)


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    version: str | None = Field(default=None, max_length=40)
    source_url: HttpUrl | None = None
    citation: str | None = Field(default=None, max_length=4000)
    conditions: Conditions | None = None
    etiological_confirmation: Etiology | None = None
    has_group_ids: bool | None = None
    role: Literal["entrenamiento", "validacion_externa", "validacion_prospectiva", "prueba_de_humo"] | None = None
    class_map: dict[str, str] | None = None
    n_images: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class LicenseIn(BaseModel):
    license_status: Literal["por_verificar", "verificada", "rechazada"]
    license: str | None = Field(default=None, max_length=200)
    license_url: HttpUrl | None = None
    license_notes: str | None = Field(default=None, max_length=4000)


class DatasetOut(ORMModel):
    id: int
    code: str
    name: str
    version: str | None
    source_url: str | None
    license: str | None
    license_url: str | None
    license_status: str
    license_notes: str | None
    license_verified_by: uuid.UUID | None
    license_verified_by_name: str | None = None
    license_verified_at: datetime | None
    citation: str | None
    conditions: str
    label_scheme: str
    etiological_confirmation: str
    has_group_ids: bool
    role: str
    class_map: dict
    n_images: int | None
    notes: str | None
    is_active: bool
    usable: bool = False
    updated_at: datetime
