"""Filtros comunes del dashboard y de los reportes sobre diagnósticos (siempre respetan el alcance del rol)."""

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, distinct, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.timeutil import day_end_utc, day_start_utc
from app.domain.labels import STATUS_VOID
from app.models import Diagnosis, Image, ModelVersion, Parcel, PotatoVariety, Ubigeo, User
from app.services.diagnosis_service import diagnosis_scope_clause
from app.services.parcel_service import _ubigeo_prefix
from app.services.scope import parcel_scope_clause


@dataclass
class FieldFilters:
    date_from: date | None = None
    date_to: date | None = None  # inclusivo (día completo en Lima)
    region_code: str | None = None
    parcel_id: int | None = None
    variety_id: int | None = None


def diagnosis_conditions(user: User, f: FieldFilters, *, include_void: bool = False,
                         dates: bool = True) -> list:
    """Condiciones WHERE para una consulta que une Diagnosis → Image → Parcel."""
    conds = []
    scope = diagnosis_scope_clause(user)
    if scope is not None:
        conds.append(scope)
    if not include_void:
        conds.append(Diagnosis.status != STATUS_VOID)
    if dates and f.date_from:
        conds.append(Diagnosis.created_at >= day_start_utc(f.date_from))
    if dates and f.date_to:
        conds.append(Diagnosis.created_at < day_end_utc(f.date_to))
    conds.extend(parcel_conditions(f))
    return conds


def parcel_conditions(f: FieldFilters) -> list:
    conds = []
    if f.region_code:
        conds.append(Parcel.region_code.startswith(_ubigeo_prefix(f.region_code)))
    if f.parcel_id:
        conds.append(Parcel.id == f.parcel_id)
    if f.variety_id:
        conds.append(Parcel.variety_id == f.variety_id)
    return conds


def diagnosis_select(*columns) -> Select:
    return (select(*columns).select_from(Diagnosis)
            .join(Image, Diagnosis.image_id == Image.id)
            .join(Parcel, Image.parcel_id == Parcel.id))


def scoped_parcels_count(db: Session, user: User, f: FieldFilters) -> int:
    stmt = select(func.count(Parcel.id)).where(Parcel.is_active.is_(True), *parcel_conditions(f))
    clause = parcel_scope_clause(user)
    if clause is not None:
        stmt = stmt.where(clause)
    return db.scalar(stmt) or 0


def current_model(db: Session) -> ModelVersion | None:
    """Modelo de referencia para encabezados: el de producción; si no hay, el usado en el último diagnóstico;
    si no hay diagnósticos, el registrado más recientemente."""
    prod = db.scalar(select(ModelVersion).where(ModelVersion.stage == "production")
                     .order_by(ModelVersion.id.desc()).limit(1))
    if prod is not None:
        return prod
    last_used = db.scalar(select(Diagnosis.model_version_id).order_by(Diagnosis.created_at.desc()).limit(1))
    if last_used is not None:
        return db.get(ModelVersion, last_used)
    return db.scalar(select(ModelVersion).order_by(ModelVersion.id.desc()).limit(1))


_SAFE_CONST = re.compile(r"^[\w /áéíóúÁÉÍÓÚñÑ+-]{1,60}$")


def const(value: str):
    """Constante de texto incrustada en el SQL (no como parámetro).

    Con psycopg 3 cada parámetro se envía por separado ($1, $2…): si una expresión con parámetros aparece en el
    SELECT y en el GROUP BY, PostgreSQL no las reconoce como iguales. Solo admite valores internos y seguros.
    """
    if not _SAFE_CONST.match(value):
        raise ValueError(f"Constante SQL no permitida: {value!r}")
    return literal_column("'" + value + "'")


def dept_code(column=None):
    """Código del departamento (DD0000) a partir del ubigeo de la parcela."""
    col = column if column is not None else Parcel.region_code
    return func.concat(func.left(col, literal_column("2")), const("0000"))


def _tz():
    from app.core.config import get_settings

    return const(get_settings().tz_display)


def local_day(column):
    """Expresión SQL: fecha local (Lima) de una columna timestamptz."""
    return func.date(func.timezone(_tz(), column))


TRUNC_UNITS = {"dia": "day", "semana": "week", "mes": "month"}


def local_period(granularity: str, column):
    """Inicio del periodo (día, semana ISO o mes) en hora local, como fecha."""
    return func.date(func.date_trunc(const(TRUNC_UNITS[granularity]), func.timezone(_tz(), column)))


def scoped_filter_options(db: Session, user: User) -> dict:
    """Regiones (departamentos con parcelas en el alcance), parcelas y variedades para los filtros."""
    scope = parcel_scope_clause(user)
    parcels_stmt = select(Parcel.id, Parcel.code, Parcel.name).order_by(Parcel.code)
    regions_stmt = select(distinct(dept_code()))
    if scope is not None:
        parcels_stmt = parcels_stmt.where(scope)
        regions_stmt = regions_stmt.where(scope)
    codes = set(db.scalars(regions_stmt).all())
    if user.region_code:
        codes.add(user.region_code[:2] + "0000")
    regions = (db.execute(select(Ubigeo.code, Ubigeo.name).where(Ubigeo.code.in_(codes)).order_by(Ubigeo.name)).all()
               if codes else [])
    varieties = db.execute(select(PotatoVariety.id, PotatoVariety.name).where(PotatoVariety.is_active.is_(True))
                           .order_by(PotatoVariety.name)).all()
    return {
        "regions": [{"code": c, "name": n} for c, n in regions],
        "parcels": [{"id": i, "code": c, "name": n} for i, c, n in db.execute(parcels_stmt).all()],
        "varieties": [{"id": i, "name": n} for i, n in varieties],
    }
