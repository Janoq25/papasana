"""Definición de datos de cada reporte (R-01 a R-10 y B-01).

Cada constructor recibe el contexto (usuario, filtros validados, límite de filas) y devuelve el resumen,
las tablas y las notas. Los datos de campo siempre respetan el alcance del rol del usuario emisor.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import Select, distinct, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.security import now_utc
from app.core.timeutil import day_end_utc, day_start_utc, to_local, today_local
from app.domain.labels import CATEGORIES, CATEGORY_LABELS, MODEL_CLASS_LABELS, STATUS_PENDING
from app.models import (
    AuditLog,
    Diagnosis,
    ExpertReview,
    Image,
    ModelVersion,
    Module,
    Parcel,
    PotatoVariety,
    Role,
    Ubigeo,
    User,
)
from app.reports.document import Column, Table
from app.reports.filters import EVENT_LABELS, GPS_LABELS, PROVENANCE_LABELS, RESULT_LABELS, STATUS_LABELS, ReportFilters
from app.services.analytics import (
    FieldFilters,
    const,
    dept_code,
    diagnosis_conditions,
    diagnosis_select,
    local_day,
    local_period,
    parcel_conditions,
)
from app.services.dashboard_service import granularity, period_starts
from app.services.scope import parcel_scope_clause


@dataclass
class BuildContext:
    db: Session
    user: User
    f: ReportFilters
    limit: int

    @property
    def ff(self) -> FieldFilters:
        return FieldFilters(self.f.date_from, self.f.date_to, self.f.region_code, self.f.parcel_id,
                            self.f.variety_id)


@dataclass
class BuildResult:
    summary: list[tuple[str, str]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# --- Utilidades ----------------------------------------------------------------------------------

def _n(v) -> str:
    return f"{int(v or 0):,}".replace(",", " ")


def _pct(part, total) -> float | None:
    return (part / total) if total else None


def _pct_s(part, total) -> str:
    p = _pct(part, total)
    return "—" if p is None else f"{p * 100:.1f} %"


def fetch_limited(db: Session, stmt: Select, limit: int) -> tuple[list, int | None]:
    """Devuelve como máximo `limit` filas y, si hay más, el total real."""
    rows = db.execute(stmt.limit(limit + 1)).all()
    if len(rows) <= limit:
        return rows, None
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return rows[:limit], total


def _cat_counts():
    return [func.count().filter(Diagnosis.category == c) for c in CATEGORIES]


CAT_COLUMNS = [Column("Sano", "int", 0.6), Column("Sospechoso", "int", 0.7),
               Column("Compatible con tizón", "int", 0.8)]

_dept_code = dept_code()


def _truncation_note(t: Table) -> None:
    if t.truncated:
        t.note = (f"Se muestran {len(t.rows):,} de {t.total_rows:,} filas. Genere el reporte en Excel para "
                  "obtener el detalle completo (hasta 50 000 filas).").replace(",", " ")


def _detail(db: Session, title: str, columns: list[Column], stmt: Select, limit: int, mapper) -> Table:
    rows, total = fetch_limited(db, stmt, limit)
    t = Table(title, columns, [mapper(r) for r in rows], total_rows=total)
    _truncation_note(t)
    return t


# --- R-01 Diagnósticos por fecha, parcela y técnico -------------------------------------------------

def build_r01(ctx: BuildContext) -> BuildResult:
    db, f = ctx.db, ctx.f
    conds = diagnosis_conditions(ctx.user, ctx.ff, include_void=f.status == "anulado")
    if f.technician_id:
        conds.append(Diagnosis.created_by == f.technician_id)
    if f.category:
        conds.append(Diagnosis.category == f.category)
    if f.status:
        conds.append(Diagnosis.status == f.status)
    tech = aliased(User)
    pending = func.count().filter(Diagnosis.status == STATUS_PENDING)

    tot = db.execute(diagnosis_select(func.count(), *_cat_counts(), pending).where(*conds)).one()
    summary = [("Diagnósticos", _n(tot[0]))] + [
        (CATEGORY_LABELS[c], f"{_n(tot[i + 1])} ({_pct_s(tot[i + 1], tot[0])})") for i, c in enumerate(CATEGORIES)
    ] + [("Pendientes de revisión", _n(tot[4]))]

    by_tech = db.execute(
        diagnosis_select(tech.full_name, tech.email, func.count(), *_cat_counts(), pending)
        .join(tech, tech.id == Diagnosis.created_by).where(*conds)
        .group_by(tech.full_name, tech.email).order_by(func.count().desc())).all()
    by_parcel = db.execute(
        diagnosis_select(Parcel.code, Parcel.name, func.count(), *_cat_counts())
        .where(*conds).group_by(Parcel.code, Parcel.name).order_by(Parcel.code)).all()

    detail = (diagnosis_select(Diagnosis.created_at, Parcel.code, tech.full_name, Diagnosis.category,
                               Diagnosis.predicted_class, Diagnosis.confidence, Diagnosis.status,
                               Diagnosis.requires_review, ModelVersion.display_name)
              .join(tech, tech.id == Diagnosis.created_by)
              .join(ModelVersion, ModelVersion.id == Diagnosis.model_version_id)
              .where(*conds).order_by(Diagnosis.created_at.desc()))
    return BuildResult(summary=summary, tables=[
        Table("Resumen por técnico",
              [Column("Técnico", width=1.6), Column("Correo", width=1.8), Column("Total", "int", 0.6),
               *CAT_COLUMNS, Column("Pendientes", "int", 0.7)],
              [[r[0], r[1], r[2], r[3], r[4], r[5], r[6]] for r in by_tech]),
        Table("Resumen por parcela",
              [Column("Código", width=1.0), Column("Parcela", width=2.0), Column("Total", "int", 0.6), *CAT_COLUMNS],
              [list(r) for r in by_parcel]),
        _detail(db, "Detalle de diagnósticos",
                [Column("Fecha y hora", "datetime", 1.1), Column("Parcela", width=1.0),
                 Column("Técnico", width=1.4), Column("Categoría", width=1.5), Column("Clase predicha", width=1.6),
                 Column("Confianza", "pct", 0.7), Column("Estado", width=1.1), Column("Requiere revisión", "bool", 0.7),
                 Column("Modelo", width=2.0)],
                detail, ctx.limit,
                lambda r: [r[0], r[1], r[2], CATEGORY_LABELS.get(r[3], r[3]), MODEL_CLASS_LABELS.get(r[4], r[4]),
                           r[5], STATUS_LABELS.get(r[6], r[6]), r[7], r[8]]),
    ])


# --- R-02 Imágenes procesadas -----------------------------------------------------------------------

def build_r02(ctx: BuildContext) -> BuildResult:
    db, f, user = ctx.db, ctx.f, ctx.user
    conds = []
    clause = parcel_scope_clause(user)
    if clause is not None:
        conds.append(or_(clause, Image.uploaded_by == user.id))
    if f.date_from:
        conds.append(Image.created_at >= day_start_utc(f.date_from))
    if f.date_to:
        conds.append(Image.created_at < day_end_utc(f.date_to))
    conds.extend(parcel_conditions(FieldFilters(region_code=f.region_code, parcel_id=f.parcel_id)))
    if f.batch_id:
        conds.append(Image.batch_id == f.batch_id)
    if f.provenance:
        conds.append(Image.provenance == f.provenance)

    def base(*cols):
        return select(*cols).select_from(Image).join(Parcel, Image.parcel_id == Parcel.id)

    no_diag = ~select(Diagnosis.id).where(Diagnosis.image_id == Image.id).exists()
    tot = db.execute(base(
        func.count(), func.count().filter(Image.gps_source != "ninguno"),
        func.count().filter(Image.inside_parcel.is_(True)), func.count().filter(Image.inside_parcel.is_(False)),
        func.count().filter(Image.duplicate_of_id.is_not(None)), func.count().filter(no_diag),
    ).where(*conds)).one()
    summary = [("Imágenes", _n(tot[0])), ("Con ubicación", f"{_n(tot[1])} ({_pct_s(tot[1], tot[0])})"),
               ("Dentro de la parcela", _n(tot[2])), ("Fuera de la parcela", _n(tot[3])),
               ("Posibles duplicados", _n(tot[4])), ("Sin diagnóstico (en cola o con error)", _n(tot[5]))]

    by_source = db.execute(base(Image.provenance, Image.gps_source, func.count()).where(*conds)
                           .group_by(Image.provenance, Image.gps_source)
                           .order_by(Image.provenance, func.count().desc())).all()
    detail = (base(Image.created_at, Image.original_filename, Parcel.code, Image.provenance, Image.gps_source,
                   Image.inside_parcel, Image.duplicate_distance, Image.width, Image.height, Image.size_bytes,
                   Image.batch_id, Diagnosis.category)
              .outerjoin(Diagnosis, Diagnosis.image_id == Image.id)
              .where(*conds).order_by(Image.created_at.desc()))
    return BuildResult(summary=summary, tables=[
        Table("Por procedencia y fuente de ubicación",
              [Column("Procedencia", width=1.2), Column("Fuente de ubicación", width=1.6),
               Column("Imágenes", "int", 0.8)],
              [[PROVENANCE_LABELS.get(r[0], r[0]), GPS_LABELS.get(r[1], r[1]), r[2]] for r in by_source]),
        _detail(db, "Detalle de imágenes",
                [Column("Fecha y hora", "datetime", 1.1), Column("Archivo", width=1.6), Column("Parcela", width=1.0),
                 Column("Procedencia", width=0.8), Column("Ubicación", width=1.3),
                 Column("Dentro de la parcela", width=0.8), Column("Distancia a duplicado", "int", 0.8),
                 Column("Dimensiones", width=0.9), Column("Tamaño (KB)", "float", 0.8), Column("Lote", width=0.8),
                 Column("Diagnóstico", width=1.4)],
                detail, ctx.limit,
                lambda r: [r[0], r[1], r[2], PROVENANCE_LABELS.get(r[3], r[3]), GPS_LABELS.get(r[4], r[4]),
                           None if r[5] is None else ("Sí" if r[5] else "No"), r[6], f"{r[7]}×{r[8]}",
                           round(r[9] / 1024, 1), str(r[10])[:8] if r[10] else None,
                           CATEGORY_LABELS.get(r[11], "Sin diagnóstico") if r[11] else "Sin diagnóstico"]),
    ])


# --- R-03 Casos pendientes de revisión -----------------------------------------------------------------

def build_r03(ctx: BuildContext) -> BuildResult:
    db, f = ctx.db, ctx.f
    conds = diagnosis_conditions(ctx.user, FieldFilters(region_code=f.region_code, parcel_id=f.parcel_id))
    conds.append(Diagnosis.status == STATUS_PENDING)
    if f.category:
        conds.append(Diagnosis.category == f.category)
    if f.min_age_days:
        conds.append(Diagnosis.created_at <= now_utc() - timedelta(days=f.min_age_days))
    age = func.extract("epoch", func.now() - Diagnosis.created_at) / 86400.0
    dept = aliased(Ubigeo)
    tech = aliased(User)

    tot = db.execute(diagnosis_select(func.count(), func.max(age), func.avg(age)).where(*conds)).one()
    summary = [("Casos pendientes", _n(tot[0])),
               ("Antigüedad máxima", "—" if tot[1] is None else f"{float(tot[1]):.1f} días"),
               ("Antigüedad promedio", "—" if tot[2] is None else f"{float(tot[2]):.1f} días")]
    by_region = db.execute(
        diagnosis_select(func.coalesce(dept.name, _dept_code), func.count(), func.max(age))
        .outerjoin(dept, dept.code == _dept_code).where(*conds)
        .group_by(dept.name, _dept_code).order_by(func.count().desc())).all()
    detail = (diagnosis_select(Diagnosis.created_at, age, Parcel.code, func.coalesce(dept.name, _dept_code),
                               tech.full_name, Diagnosis.category, Diagnosis.predicted_class, Diagnosis.confidence)
              .outerjoin(dept, dept.code == _dept_code).join(tech, tech.id == Diagnosis.created_by)
              .where(*conds).order_by(Diagnosis.created_at.asc()))
    return BuildResult(summary=summary, tables=[
        Table("Pendientes por región", [Column("Región", width=1.5), Column("Casos", "int", 0.7),
                                        Column("Antigüedad máxima (días)", "float", 1.0)],
              [[r[0], r[1], float(r[2]) if r[2] is not None else None] for r in by_region]),
        _detail(db, "Casos pendientes (los más antiguos primero)",
                [Column("Fecha y hora", "datetime", 1.1), Column("Antigüedad (días)", "float", 0.8),
                 Column("Parcela", width=1.0), Column("Región", width=1.0), Column("Técnico", width=1.4),
                 Column("Categoría", width=1.5), Column("Clase predicha", width=1.6), Column("Confianza", "pct", 0.7)],
                detail, ctx.limit,
                lambda r: [r[0], float(r[1]), r[2], r[3], r[4], CATEGORY_LABELS.get(r[5], r[5]),
                           MODEL_CLASS_LABELS.get(r[6], r[6]), r[7]]),
    ])


# --- R-04 Alertas emitidas (Fase 5) -----------------------------------------------------------------------

def build_r04(ctx: BuildContext) -> BuildResult:
    return BuildResult(
        summary=[("Alertas emitidas", "0")],
        tables=[Table("Alertas emitidas",
                      [Column("Fecha y hora", "datetime", 1.1), Column("Nivel", width=0.7),
                       Column("Parcela", width=1.0),
                       Column("Región", width=1.0), Column("Riesgo climático", width=1.0),
                       Column("Diagnósticos compatibles", "int", 0.9), Column("Estado", width=0.8),
                       Column("Canal de envío", width=0.9)], [])],
        notes=["El módulo de riesgo climático y alertas se implementa en la Fase 5. El reporte ya tiene su "
               "formato definitivo, pero todavía no hay alertas registradas."],
    )


# --- R-05 Actividad de usuarios (bitácora) ------------------------------------------------------------------

def _audit_conditions(f: ReportFilters) -> list:
    conds = []
    if f.user_email:
        conds.append(func.lower(AuditLog.user_email).like(f"%{f.user_email.lower()}%"))
    if f.role_code:
        conds.append(AuditLog.role_code == f.role_code)
    if f.module_code:
        conds.append(AuditLog.module_code == f.module_code)
    if f.event_type:
        conds.append(AuditLog.event_type == f.event_type)
    if f.result:
        conds.append(AuditLog.result == f.result)
    if f.date_from:
        conds.append(AuditLog.occurred_at >= day_start_utc(f.date_from))
    if f.date_to:
        conds.append(AuditLog.occurred_at < day_end_utc(f.date_to))
    return conds


def _module_names(db: Session) -> dict[str, str]:
    return dict(db.execute(select(Module.code, Module.name)).all())


def _role_names(db: Session) -> dict[str, str]:
    return dict(db.execute(select(Role.code, Role.name)).all())


def _module_time(db: Session, conds: list, modules: dict[str, str]) -> Table:
    rows = db.execute(select(AuditLog.module_code, func.count(), func.sum(AuditLog.duration_ms),
                             func.avg(AuditLog.duration_ms))
                      .where(AuditLog.event_type == "modulo_salida", *conds)
                      .group_by(AuditLog.module_code).order_by(func.sum(AuditLog.duration_ms).desc())).all()
    return Table("Permanencia por módulo",
                 [Column("Módulo", width=1.6), Column("Visitas", "int", 0.7), Column("Tiempo total", "hours", 0.9),
                  Column("Promedio por visita", "minutes", 0.9)],
                 [[modules.get(r[0], r[0]), r[1], (r[2] or 0) / 3_600_000,
                   (float(r[3]) / 60_000) if r[3] is not None else None] for r in rows])


def build_r05(ctx: BuildContext) -> BuildResult:
    db = ctx.db
    conds = _audit_conditions(ctx.f)
    modules, roles = _module_names(db), _role_names(db)
    ev = AuditLog.event_type
    tot = db.execute(select(func.count(), func.count(distinct(AuditLog.user_email)),
                            func.count().filter(ev == "login"), func.count().filter(ev == "login_fallido"),
                            func.count().filter(ev == "acceso_denegado")).where(*conds)).one()
    summary = [("Eventos", _n(tot[0])), ("Usuarios distintos", _n(tot[1])), ("Inicios de sesión", _n(tot[2])),
               ("Inicios de sesión fallidos", _n(tot[3])), ("Accesos denegados", _n(tot[4]))]
    by_user = db.execute(select(AuditLog.user_email, AuditLog.role_code, func.count(),
                                func.count().filter(ev == "login"), func.count().filter(ev == "accion"),
                                func.count().filter(ev == "acceso_denegado"), func.max(AuditLog.occurred_at))
                         .where(*conds).group_by(AuditLog.user_email, AuditLog.role_code)
                         .order_by(func.count().desc())).all()
    detail = (select(AuditLog.occurred_at, AuditLog.user_email, AuditLog.role_code, AuditLog.event_type,
                     AuditLog.module_code, AuditLog.action, AuditLog.result, AuditLog.ip)
              .where(*conds).order_by(AuditLog.seq.desc()))
    return BuildResult(summary=summary, tables=[
        Table("Actividad por usuario",
              [Column("Usuario", width=1.8), Column("Rol", width=1.2), Column("Eventos", "int", 0.6),
               Column("Inicios de sesión", "int", 0.7), Column("Acciones", "int", 0.6),
               Column("Accesos denegados", "int", 0.7), Column("Última actividad", "datetime", 1.1)],
              [[r[0] or "(anónimo)", roles.get(r[1], r[1]), r[2], r[3], r[4], r[5], r[6]] for r in by_user]),
        _module_time(db, conds, modules),
        _detail(db, "Eventos (los más recientes primero)",
                [Column("Fecha y hora", "datetime", 1.1), Column("Usuario", width=1.7), Column("Rol", width=1.1),
                 Column("Evento", width=1.1), Column("Módulo", width=1.2), Column("Acción", width=1.0),
                 Column("Resultado", width=0.6), Column("IP", width=0.9)],
                detail, ctx.limit,
                lambda r: [r[0], r[1], roles.get(r[2], r[2]), EVENT_LABELS.get(r[3], r[3]),
                           modules.get(r[4], r[4]), r[5], RESULT_LABELS.get(r[6], r[6]),
                           str(r[7]) if r[7] is not None else None]),
    ])


# --- R-06 Incidencia por región y variedad -------------------------------------------------------------------

def build_r06(ctx: BuildContext) -> BuildResult:
    db = ctx.db
    conds = diagnosis_conditions(ctx.user, ctx.ff)
    dept = aliased(Ubigeo)
    variety = func.coalesce(PotatoVariety.name, const("Sin variedad"))
    confirmed = func.count(ExpertReview.id).filter(ExpertReview.final_label == "tizon_tardio_confirmado")

    def grouped(*keys):
        return (diagnosis_select(*keys, func.count(), *_cat_counts(), confirmed)
                .outerjoin(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id)
                .outerjoin(dept, dept.code == _dept_code)
                .outerjoin(PotatoVariety, PotatoVariety.id == Parcel.variety_id)
                .where(*conds))

    region_name = func.coalesce(dept.name, _dept_code)
    by_region = db.execute(grouped(region_name).group_by(region_name).order_by(func.count().desc())).all()
    by_variety = db.execute(grouped(variety).group_by(variety).order_by(func.count().desc())).all()
    cross = db.execute(grouped(region_name, variety).group_by(region_name, variety)
                       .order_by(region_name, func.count().desc())).all()
    total = sum(r[1] for r in by_region)
    compat = sum(r[4] for r in by_region)

    cols = [Column("Total", "int", 0.6), *CAT_COLUMNS, Column("% compatible", "pct", 0.8),
            Column("Confirmados por experto", "int", 0.9)]

    def rows(data, nkeys):
        return [[*r[:nkeys], r[nkeys], r[nkeys + 1], r[nkeys + 2], r[nkeys + 3], _pct(r[nkeys + 3], r[nkeys]),
                 r[nkeys + 4]] for r in data]

    return BuildResult(
        summary=[("Diagnósticos", _n(total)),
                 ("Compatibles con tizón tardío", f"{_n(compat)} ({_pct_s(compat, total)})"),
                 ("Regiones con datos", _n(len(by_region))), ("Variedades con datos", _n(len(by_variety)))],
        tables=[
            Table("Por región", [Column("Región", width=1.4), *cols], rows(by_region, 1)),
            Table("Por variedad", [Column("Variedad", width=1.4), *cols], rows(by_variety, 1)),
            Table("Región × variedad", [Column("Región", width=1.2), Column("Variedad", width=1.2), *cols],
                  rows(cross, 2)),
        ],
        notes=["La incidencia se expresa como proporción de fotografías diagnosticadas en cada categoría. No es una "
               "estimación epidemiológica de la incidencia en campo: depende de qué plantas se fotografían y con "
               "qué frecuencia."],
    )


# --- R-07 Tendencias temporales ------------------------------------------------------------------------------

_GRAN_LABEL = {"dia": "Día", "semana": "Semana (inicia el lunes)", "mes": "Mes"}


def build_r07(ctx: BuildContext) -> BuildResult:
    db, f = ctx.db, ctx.f
    conds = diagnosis_conditions(ctx.user, ctx.ff)
    end = f.date_to or today_local()
    if f.date_from:
        start = f.date_from
    else:
        first = db.scalar(diagnosis_select(func.min(Diagnosis.created_at)).where(*conds))
        start = to_local(first).date() if first else end
    start = min(start, end)
    gran = f.aggregation or granularity(start, end)
    period = local_period(gran, Diagnosis.created_at)
    data = db.execute(diagnosis_select(period, func.count(), *_cat_counts(),
                                       func.count().filter(Diagnosis.status == STATUS_PENDING),
                                       func.count().filter(Diagnosis.status.in_(("validado", "corregido"))))
                      .where(*conds).group_by(period).order_by(period)).all()
    found = {r[0]: r for r in data}
    rows = []
    for p in period_starts(start, end, gran):
        r = found.get(p)
        vals = [int(x) for x in r[1:]] if r else [0] * 6
        rows.append([p, vals[0], vals[1], vals[2], vals[3], _pct(vals[3], vals[0]), vals[4], vals[5]])
    total = sum(r[1] for r in rows)
    return BuildResult(
        summary=[("Periodo", f"{start:%d/%m/%Y} a {end:%d/%m/%Y}"), ("Agregación", _GRAN_LABEL[gran]),
                 ("Diagnósticos", _n(total)), ("Periodos", _n(len(rows)))],
        tables=[Table(f"Tendencia ({_GRAN_LABEL[gran].lower()})",
                      [Column(_GRAN_LABEL[gran].split(" ")[0], "date", 0.9), Column("Total", "int", 0.6), *CAT_COLUMNS,
                       Column("% compatible", "pct", 0.8), Column("Pendientes", "int", 0.7),
                       Column("Revisados por experto", "int", 0.9)], rows)],
    )


# --- R-08 Desempeño y deriva de los modelos ---------------------------------------------------------------------

def _agreement(confirms: int, corrects: int) -> float | None:
    n = confirms + corrects
    return confirms / n if n else None


def build_r08(ctx: BuildContext) -> BuildResult:
    db, f = ctx.db, ctx.f
    conds = diagnosis_conditions(ctx.user, ctx.ff)
    if f.model_version_id:
        conds.append(Diagnosis.model_version_id == f.model_version_id)
    confirms = func.count(ExpertReview.id).filter(ExpertReview.decision == "confirma")
    corrects = func.count(ExpertReview.id).filter(ExpertReview.decision == "corrige")
    metrics = (func.count(Diagnosis.id), func.avg(Diagnosis.confidence),
               func.count().filter(Diagnosis.requires_review.is_(True)), func.count(ExpertReview.id),
               confirms, corrects)

    by_model = db.execute(
        diagnosis_select(ModelVersion.display_name, ModelVersion.stage, ModelVersion.is_demo, *metrics,
                         func.avg(Diagnosis.inference_ms))
        .join(ModelVersion, ModelVersion.id == Diagnosis.model_version_id)
        .outerjoin(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id).where(*conds)
        .group_by(ModelVersion.display_name, ModelVersion.stage, ModelVersion.is_demo)
        .order_by(func.count(Diagnosis.id).desc())).all()

    window = f.window or "semana"
    period = local_period(window, Diagnosis.created_at)
    by_window = db.execute(
        diagnosis_select(period, ModelVersion.display_name, *metrics)
        .join(ModelVersion, ModelVersion.id == Diagnosis.model_version_id)
        .outerjoin(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id).where(*conds)
        .group_by(period, ModelVersion.display_name).order_by(period, ModelVersion.display_name)).all()

    any_demo = any(r[2] for r in by_model)
    notes = ["Acuerdo con experto = casos en que el especialista confirmó la predicción ÷ casos confirmados o "
             "corregidos (se excluyen los 'no determinables'). Solo se calcula sobre los casos revisados, que no "
             "son una muestra aleatoria: es un indicador de seguimiento, no una métrica de evaluación.",
             "La deriva por distancia de embeddings frente al conjunto de entrenamiento se incorpora con el "
             "monitoreo de deriva (módulo A3, fases 4 y 5)."]
    if any_demo:
        notes.insert(0, "Con el modelo DEMO las cifras solo prueban el cálculo: no describen desempeño diagnóstico.")
    return BuildResult(
        summary=[("Versiones de modelo con datos", _n(len(by_model))),
                 ("Diagnósticos", _n(sum(r[3] for r in by_model))),
                 ("Revisados por experto", _n(sum(r[6] for r in by_model)))],
        tables=[
            Table("Por versión de modelo",
                  [Column("Modelo", width=2.2), Column("Etapa", width=0.7), Column("DEMO", "bool", 0.5),
                   Column("Diagnósticos", "int", 0.7), Column("Confianza media", "pct", 0.8),
                   Column("% requiere revisión", "pct", 0.8), Column("Revisados", "int", 0.7),
                   Column("Acuerdo con experto", "pct", 0.8), Column("Inferencia media", "ms", 0.8)],
                  [[r[0], r[1], r[2], r[3], float(r[4]) if r[4] is not None else None, _pct(r[5], r[3]), r[6],
                    _agreement(r[7], r[8]), float(r[9]) if r[9] is not None else None] for r in by_model]),
            Table(f"Evolución {'semanal' if window == 'semana' else 'mensual'}",
                  [Column("Periodo", "date", 0.8), Column("Modelo", width=2.0), Column("Diagnósticos", "int", 0.7),
                   Column("Confianza media", "pct", 0.8), Column("% requiere revisión", "pct", 0.8),
                   Column("Revisados", "int", 0.7), Column("Acuerdo con experto", "pct", 0.8)],
                  [[r[0], r[1], r[2], float(r[3]) if r[3] is not None else None, _pct(r[4], r[2]), r[5],
                    _agreement(r[6], r[7])] for r in by_window]),
        ],
        notes=notes,
    )


# --- R-09 Tiempos de respuesta ----------------------------------------------------------------------------------

def build_r09(ctx: BuildContext) -> BuildResult:
    db = ctx.db
    conds = diagnosis_conditions(ctx.user, ctx.ff)
    ms = Diagnosis.inference_ms
    inf = db.execute(
        diagnosis_select(ModelVersion.display_name, func.count(ms), func.avg(ms),
                         func.percentile_cont(0.5).within_group(ms), func.percentile_cont(0.95).within_group(ms),
                         func.max(ms))
        .join(ModelVersion, ModelVersion.id == Diagnosis.model_version_id)
        .where(*conds, ms.is_not(None)).group_by(ModelVersion.display_name)).all()

    hours = func.extract("epoch", ExpertReview.created_at - Diagnosis.created_at) / 3600.0
    stats = (func.count(), func.avg(hours), func.percentile_cont(0.5).within_group(hours),
             func.percentile_cont(0.95).within_group(hours), func.max(hours))
    rev_total = db.execute(diagnosis_select(*stats).join(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id)
                           .where(*conds)).one()
    reviewer = aliased(User)
    by_reviewer = db.execute(
        diagnosis_select(reviewer.full_name, *stats).join(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id)
        .join(reviewer, reviewer.id == ExpertReview.reviewer_id).where(*conds)
        .group_by(reviewer.full_name).order_by(func.count().desc())).all()

    def f(v):
        return float(v) if v is not None else None

    n_inf = sum(r[1] for r in inf)
    stat_cols = [Column("Casos", "int", 0.6), Column("Media", "hours", 0.7), Column("Mediana", "hours", 0.7),
                 Column("Percentil 95", "hours", 0.7), Column("Máximo", "hours", 0.7)]
    return BuildResult(
        summary=[("Inferencias medidas", _n(n_inf)),
                 ("Casos revisados por experto", _n(rev_total[0])),
                 ("Mediana hasta la revisión", "—" if rev_total[2] is None else f"{float(rev_total[2]):.1f} h")],
        tables=[
            Table("Tiempo de inferencia por modelo",
                  [Column("Modelo", width=2.2), Column("Inferencias", "int", 0.7), Column("Media", "ms", 0.7),
                   Column("Mediana", "ms", 0.7), Column("Percentil 95", "ms", 0.7), Column("Máximo", "ms", 0.7)],
                  [[r[0], r[1], f(r[2]), f(r[3]), f(r[4]), f(r[5])] for r in inf],
                  note="Tiempo medido dentro de ml-service (preprocesamiento, inferencia y Grad-CAM); "
                       "no incluye la red "
                       "ni la carga del archivo."),
            Table("Tiempo hasta la revisión experta (todos los especialistas)", stat_cols,
                  [[rev_total[0], f(rev_total[1]), f(rev_total[2]), f(rev_total[3]), f(rev_total[4])]]
                  if rev_total[0] else []),
            Table("Tiempo hasta la revisión por especialista", [Column("Especialista", width=1.8), *stat_cols],
                  [[r[0], r[1], f(r[2]), f(r[3]), f(r[4]), f(r[5])] for r in by_reviewer]),
        ],
    )


# --- R-10 Uso del sistema ------------------------------------------------------------------------------------------

def build_r10(ctx: BuildContext) -> BuildResult:
    db = ctx.db
    conds = _audit_conditions(ReportFilters(date_from=ctx.f.date_from, date_to=ctx.f.date_to,
                                            role_code=ctx.f.role_code))
    modules, roles = _module_names(db), _role_names(db)
    ev = AuditLog.event_type
    login_users = func.count(distinct(AuditLog.user_email)).filter(ev == "login")
    tot = db.execute(select(func.count().filter(ev == "login"), login_users,
                            func.count().filter(ev == "login_fallido"), func.count().filter(ev == "sesion_expirada"),
                            func.count().filter(ev == "logout")).where(*conds)).one()
    by_role = db.execute(select(AuditLog.role_code, func.count().filter(ev == "login"), login_users,
                                func.count().filter(ev == "sesion_expirada"),
                                func.sum(AuditLog.duration_ms).filter(ev == "modulo_salida"))
                         .where(*conds, AuditLog.role_code.is_not(None)).group_by(AuditLog.role_code)
                         .order_by(func.count().filter(ev == "login").desc())).all()
    day = local_day(AuditLog.occurred_at)
    daily = db.execute(select(day, func.count().filter(ev == "login"), login_users, func.count().filter(ev == "accion"))
                       .where(*conds).group_by(day).order_by(day)).all()
    return BuildResult(
        summary=[("Inicios de sesión", _n(tot[0])), ("Usuarios que iniciaron sesión", _n(tot[1])),
                 ("Inicios de sesión fallidos", _n(tot[2])), ("Sesiones cerradas por inactividad", _n(tot[3])),
                 ("Cierres de sesión", _n(tot[4]))],
        tables=[
            Table("Sesiones por rol",
                  [Column("Rol", width=1.6), Column("Inicios de sesión", "int", 0.8), Column("Usuarios", "int", 0.6),
                   Column("Expiradas por inactividad", "int", 0.9), Column("Tiempo en módulos", "hours", 0.9)],
                  [[roles.get(r[0], r[0]), r[1], r[2], r[3], (r[4] or 0) / 3_600_000] for r in by_role]),
            _module_time(db, conds, modules),
            Table("Actividad diaria",
                  [Column("Fecha", "date", 0.8), Column("Inicios de sesión", "int", 0.8),
                   Column("Usuarios", "int", 0.6),
                   Column("Acciones", "int", 0.7)],
                  [list(r) for r in daily]),
        ],
    )


# --- B-01 Bitácora de auditoría (exportación) -------------------------------------------------------------------------

def build_b01(ctx: BuildContext) -> BuildResult:
    from app.services.audit_service import AuditService

    db = ctx.db
    f = ctx.f
    conds = _audit_conditions(ReportFilters(user_email=f.user_email, module_code=f.module_code,
                                            event_type=f.event_type, result=f.result, date_from=f.date_from,
                                            date_to=f.date_to))
    modules, roles = _module_names(db), _role_names(db)
    total = db.scalar(select(func.count()).select_from(AuditLog).where(*conds)) or 0
    check = AuditService(db).verify()
    if check["ok"]:
        integrity = f"Íntegra ({_n(check['total_registros'])} registros verificados)"
    else:
        broken = check["primer_registro_alterado"] or {}
        integrity = f"ALTERADA: primer registro con problema seq {broken.get('seq')} ({broken.get('motivo')})"
    detail = (select(AuditLog.seq, AuditLog.occurred_at, AuditLog.user_email, AuditLog.role_code, AuditLog.event_type,
                     AuditLog.module_code, AuditLog.action, AuditLog.entity_type, AuditLog.entity_id, AuditLog.result,
                     AuditLog.ip, AuditLog.duration_ms, AuditLog.hash, AuditLog.prev_hash, AuditLog.before,
                     AuditLog.after, AuditLog.endpoint, AuditLog.user_agent)
              .where(*conds).order_by(AuditLog.seq.asc()))
    return BuildResult(
        summary=[("Registros que cumplen los filtros", _n(total)),
                 ("Cadena de hash (verificación completa)", integrity)],
        tables=[_detail(db, "Registros de la bitácora (orden cronológico)",
                        [Column("Seq", "int", 0.5), Column("Fecha y hora", "datetime", 1.0),
                         Column("Usuario", width=1.6), Column("Rol", width=1.0), Column("Evento", width=1.0),
                         Column("Módulo", width=1.0), Column("Acción", width=0.9), Column("Entidad", width=0.8),
                         Column("ID entidad", width=1.0), Column("Resultado", width=0.6), Column("IP", width=0.8),
                         Column("Duración", "ms", 0.7), Column("Hash", "hash", 1.0),
                         Column("Hash anterior", "hash", xlsx_only=True), Column("Antes", "json", xlsx_only=True),
                         Column("Después", "json", xlsx_only=True), Column("Endpoint", xlsx_only=True),
                         Column("User-agent", xlsx_only=True)],
                        detail, ctx.limit,
                        lambda r: [r[0], r[1], r[2], roles.get(r[3], r[3]), EVENT_LABELS.get(r[4], r[4]),
                                   modules.get(r[5], r[5]), r[6], r[7], r[8], RESULT_LABELS.get(r[9], r[9]),
                                   str(r[10]) if r[10] is not None else None,
                                   r[11], r[12], r[13], r[14], r[15], r[16], r[17]])],
        notes=["Las horas están en la zona America/Lima. La columna Hash muestra los primeros 16 caracteres en PDF y "
               "Word; Excel incluye el hash completo, el hash anterior y los valores antes/después."],
    )
