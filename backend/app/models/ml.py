"""Esquema `ml`: versiones de modelo, promociones (cuatro ojos) y registro de datasets con licencias (A1)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelVersion(Base):
    """Versiones de modelo: el DEMO (D-16) y las versiones registradas en el Model Registry de MLflow.

    `model_key` es el identificador que reporta ml-service: `demo-…` o `<modelo registrado>:v<versión>`.
    La etapa `production` refleja el alias `production` de MLflow (la fuente de verdad del modelo en uso).
    """

    __tablename__ = "model_versions"
    __table_args__ = {"schema": "ml"}

    id: Mapped[int] = mapped_column(primary_key=True)
    model_key: Mapped[str] = mapped_column(String(80), unique=True)
    architecture: Mapped[str] = mapped_column(String(40))
    display_name: Mapped[str] = mapped_column(String(160))
    mlflow_model_name: Mapped[str | None] = mapped_column(String(120))
    mlflow_version: Mapped[str | None] = mapped_column(String(20))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(10), default="demo", server_default="demo")  # demo | mlflow
    stage: Mapped[str] = mapped_column(String(15), default="demo")  # demo|staging|production|archived
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    smoke_test: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    label_scheme: Mapped[str] = mapped_column(String(15), default="sintoma")  # sintoma | patogeno
    classes: Mapped[list] = mapped_column(JSONB)
    temperature: Mapped[float] = mapped_column(Float, default=1.0)
    train_dataset_ids: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    metrics_summary: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelPromotion(Base):
    """Solicitud de promoción o rollback: la propone el Investigador y la aprueba otra persona (D-09)."""

    __tablename__ = "model_promotions"
    __table_args__ = {"schema": "ml"}

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("ml.model_versions.id"), index=True)
    action: Mapped[str] = mapped_column(String(10))  # promover | rollback
    status: Mapped[str] = mapped_column(String(12), default="pendiente", index=True)
    # pendiente | aplicada | rechazada | cancelada | fallida
    from_stage: Mapped[str | None] = mapped_column(String(15))
    to_stage: Mapped[str] = mapped_column(String(15), default="production")
    previous_model_version_id: Mapped[int | None] = mapped_column(ForeignKey("ml.model_versions.id"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("seguridad.users.id"))
    request_reason: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seguridad.users.id"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model_version: Mapped[ModelVersion] = relationship(foreign_keys=[model_version_id], lazy="joined")
    previous: Mapped[ModelVersion | None] = relationship(foreign_keys=[previous_model_version_id], lazy="joined")


class Dataset(Base):
    """Registro de datasets y licencias (módulo A1). Espejo editable de `ml/datasets.yaml`."""

    __tablename__ = "datasets"
    __table_args__ = {"schema": "ml"}

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str | None] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str | None] = mapped_column(String(200))
    license_url: Mapped[str | None] = mapped_column(String(500))
    license_status: Mapped[str] = mapped_column(String(15), default="por_verificar", index=True)
    # por_verificar | verificada | rechazada
    license_notes: Mapped[str | None] = mapped_column(Text)
    license_verified_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seguridad.users.id"))
    license_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    citation: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[str] = mapped_column(String(20))  # laboratorio | campo | mixto | sintetico
    label_scheme: Mapped[str] = mapped_column(String(15), default="sintoma")
    etiological_confirmation: Mapped[str] = mapped_column(String(10), default="no")  # no | parcial | si
    has_group_ids: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(30))
    class_map: Mapped[dict] = mapped_column(JSONB, default=dict)
    n_images: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("seguridad.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
