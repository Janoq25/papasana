from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SCHEMA = "catalogo"


class Ubigeo(Base):
    """Ubigeo INEI (departamento, provincia, distrito). Se siembran los departamentos; el resto se importa (CSV)."""

    __tablename__ = "ubigeo"
    __table_args__ = {"schema": SCHEMA}

    code: Mapped[str] = mapped_column(String(6), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(15))  # departamento | provincia | distrito
    parent_code: Mapped[str | None] = mapped_column(ForeignKey(f"{SCHEMA}.ubigeo.code"))


class _CatalogMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PotatoVariety(_CatalogMixin, Base):
    __tablename__ = "potato_varieties"
    __table_args__ = {"schema": SCHEMA}

    group: Mapped[str | None] = mapped_column(String(30))  # nativa | mejorada
    # Susceptibilidad al tizón tardío: solo con fuente verificable (si no, queda vacía)
    late_blight_susceptibility: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(Text)


class PhenologicalStage(_CatalogMixin, Base):
    __tablename__ = "phenological_stages"
    __table_args__ = {"schema": SCHEMA}

    code: Mapped[str] = mapped_column(String(30), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(Text)


class DifferentialDisease(_CatalogMixin, Base):
    __tablename__ = "differential_diseases"
    __table_args__ = {"schema": SCHEMA}

    causal_agent: Mapped[str | None] = mapped_column(String(160))
    key_symptoms: Mapped[str | None] = mapped_column(Text)
    distinguishing_features: Mapped[str | None] = mapped_column(Text)
    # True para la enfermedad objetivo del sistema (tizón tardío); False para diferenciales
    is_target: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(Text)
