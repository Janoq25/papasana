import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

# --- Catálogos ----------------------------------------------------------------------------------


class VarietyIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    group: Literal["nativa", "mejorada"] | None = None
    late_blight_susceptibility: Literal["alta", "media", "baja"] | None = None
    source: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class StageIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(pattern=r"^[a-z_]{2,30}$")
    sort_order: int = Field(default=0, ge=0, le=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class DiseaseIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    causal_agent: str | None = Field(default=None, max_length=160)
    key_symptoms: str | None = Field(default=None, max_length=1000)
    distinguishing_features: str | None = Field(default=None, max_length=1000)
    source: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class CatalogItemOut(ORMModel):
    id: int
    name: str
    is_active: bool
    group: str | None = None
    late_blight_susceptibility: str | None = None
    source: str | None = None
    code: str | None = None
    sort_order: int | None = None
    description: str | None = None
    causal_agent: str | None = None
    key_symptoms: str | None = None
    distinguishing_features: str | None = None
    is_target: bool | None = None


# --- Productores y parcelas -------------------------------------------------------------------


class ProducerIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    contact: str | None = Field(default=None, max_length=160)
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class ProducerOut(ORMModel):
    id: int
    name: str
    contact: str | None
    region_code: str | None


class PolygonIn(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]] = Field(min_length=1, max_length=1)


class ParcelIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-_]{2,30}$")
    region_code: str = Field(pattern=r"^\d{6}$")
    producer_id: int | None = None
    variety_id: int | None = None
    sowing_date: date | None = None
    phenological_stage_id: int | None = None
    altitude_m: int | None = Field(default=None, ge=0, le=5500)
    notes: str | None = Field(default=None, max_length=1000)
    geometry: PolygonIn


class ParcelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    region_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    producer_id: int | None = None
    variety_id: int | None = None
    sowing_date: date | None = None
    phenological_stage_id: int | None = None
    altitude_m: int | None = Field(default=None, ge=0, le=5500)
    notes: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    geometry: PolygonIn | None = None


class ParcelOut(BaseModel):
    id: int
    code: str
    name: str
    region_code: str
    producer: ProducerOut | None
    variety: CatalogItemOut | None
    stage: CatalogItemOut | None
    sowing_date: date | None
    altitude_m: int | None
    area_ha: float
    notes: str | None
    is_active: bool
    geometry: dict | None = None
    centroid: list[float] | None = None
    assignees: list[uuid.UUID] = []
    created_at: datetime


class AssignmentsIn(BaseModel):
    user_ids: list[uuid.UUID] = Field(max_length=100)


class AssignableUserOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role_name: str


# --- Diagnóstico --------------------------------------------------------------------------------


class ModelVersionOut(ORMModel):
    id: int
    model_key: str
    display_name: str
    architecture: str
    stage: str
    is_demo: bool
    label_scheme: str
    classes: list


class ImageOut(BaseModel):
    id: uuid.UUID
    original_filename: str | None
    width: int
    height: int
    size_bytes: int
    captured_at: datetime | None
    gps_source: str
    location: dict | None
    inside_parcel: bool | None
    exif: dict
    provenance: str
    duplicate_of_id: uuid.UUID | None
    duplicate_distance: int | None


class ReviewOut(BaseModel):
    id: int
    reviewer_id: uuid.UUID
    decision: str
    final_label: str
    final_label_name: str
    evidence: str | None
    differential: str | None
    notes: str | None
    created_at: datetime


class DiagnosisOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: str
    category: str
    category_label: str
    predicted_class: str
    probabilities: dict[str, float]
    confidence: float
    threshold_used: float
    requires_review: bool
    has_gradcam: bool
    inference_ms: int | None
    void_reason: str | None
    model: ModelVersionOut
    parcel: dict
    image: ImageOut
    reviews: list[ReviewOut] = []
    created_by: uuid.UUID
    disclaimer: str


class BatchOut(BaseModel):
    id: uuid.UUID
    status: str
    total: int
    processed: int
    failed: int
    created_at: datetime
    results: list[dict[str, Any]] = []
    diagnoses: list[DiagnosisOut] = []


class VoidIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ReviewIn(BaseModel):
    final_label: Literal["sano", "tizon_tardio_sintomas", "tizon_tardio_confirmado", "otra_enfermedad",
                         "no_determinable"]
    evidence: Literal["esporulacion", "laboratorio", "camara_humeda", "otro"] | None = None
    differential_disease_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)
