"""Esquema `campo`: productores, parcelas, imágenes, diagnósticos y validación experta."""

import uuid
from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.catalog import DifferentialDisease, PhenologicalStage, PotatoVariety
from app.models.ml import ModelVersion

SCHEMA = "campo"


class Producer(Base):
    __tablename__ = "producers"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    contact: Mapped[str | None] = mapped_column(String(160))
    region_code: Mapped[str | None] = mapped_column(ForeignKey("catalogo.ubigeo.code"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seguridad.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Parcel(Base):
    __tablename__ = "parcels"
    __table_args__ = (Index("gix_campo_parcels_geom", "geom", postgresql_using="gist"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    producer_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.producers.id"))
    region_code: Mapped[str] = mapped_column(ForeignKey("catalogo.ubigeo.code"), index=True)
    variety_id: Mapped[int | None] = mapped_column(ForeignKey("catalogo.potato_varieties.id"))
    sowing_date: Mapped[date | None] = mapped_column(Date)
    phenological_stage_id: Mapped[int | None] = mapped_column(ForeignKey("catalogo.phenological_stages.id"))
    altitude_m: Mapped[int | None] = mapped_column(Integer)
    geom = mapped_column(Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False)
    centroid = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seguridad.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    producer: Mapped[Producer | None] = relationship(lazy="joined")
    variety: Mapped[PotatoVariety | None] = relationship(lazy="joined")
    stage: Mapped[PhenologicalStage | None] = relationship(lazy="joined")


class ParcelAssignment(Base):
    __tablename__ = "parcel_assignments"
    __table_args__ = {"schema": SCHEMA}

    parcel_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.parcels.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"), primary_key=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UploadBatch(Base):
    __tablename__ = "upload_batches"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"))
    parcel_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.parcels.id"))
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(15), default="procesando")  # procesando | completado
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (
        UniqueConstraint("parcel_id", "sha256"),
        Index("gix_campo_images_location", "location", postgresql_using="gist"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_key: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[int] = mapped_column(BigInteger, index=True)  # dHash de 64 bits (con signo)
    mime: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    exif: Mapped[dict] = mapped_column(JSONB, default=dict)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location = mapped_column(Geometry("POINT", srid=4326, spatial_index=False), nullable=True)
    gps_source: Mapped[str] = mapped_column(String(12), default="ninguno")  # exif|dispositivo|manual|ninguno
    inside_parcel: Mapped[bool | None] = mapped_column(Boolean)
    parcel_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.parcels.id"), index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.upload_batches.id"))
    provenance: Mapped[str] = mapped_column(String(12), default="web")  # web | movil | n8n
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{SCHEMA}.images.id"))
    duplicate_distance: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    parcel: Mapped[Parcel] = relationship(lazy="joined")


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.images.id"), index=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("ml.model_versions.id"))
    predicted_class: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(30), index=True)  # categoría mostrada (D-01)
    probabilities: Mapped[dict] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float)
    threshold_used: Mapped[float] = mapped_column(Float)
    requires_review: Mapped[bool] = mapped_column(Boolean, index=True)
    status: Mapped[str] = mapped_column(String(25), index=True)
    gradcam_key: Mapped[str | None] = mapped_column(String(255))
    inference_ms: Mapped[int | None] = mapped_column(Integer)
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    image: Mapped[Image] = relationship(lazy="joined")
    model_version: Mapped[ModelVersion] = relationship(lazy="joined")


class ExpertReview(Base):
    __tablename__ = "expert_reviews"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnosis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.diagnoses.id"), index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"))
    decision: Mapped[str] = mapped_column(String(20))  # confirma | corrige | no_determinable
    final_label: Mapped[str] = mapped_column(String(40))
    evidence: Mapped[str | None] = mapped_column(String(30))  # requerido para "tizon_tardio_confirmado"
    differential_disease_id: Mapped[int | None] = mapped_column(ForeignKey("catalogo.differential_diseases.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    differential: Mapped[DifferentialDisease | None] = relationship(lazy="joined")
