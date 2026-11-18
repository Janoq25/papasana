"""Dashboard (M03): KPIs, tendencia, distribución por región y variedad, y puntos del mapa de calor.

Todo se calcula sobre los diagnósticos no anulados dentro del alcance del rol y de los filtros globales.
No se muestra ninguna métrica que no exista: los indicadores de las fases 4 y 5 se devuelven como
"no disponibles" con el motivo (docs/decisiones.md D-40).
"""

from datetime import date, timedelta

from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.core.timeutil import day_end_utc, day_start_utc, to_local, today_local
from app.domain.labels import CATEGORIES, CATEGORY_LABELS, CATEGORY_TIZON, STATUS_PENDING
from app.models import Diagnosis, ExpertReview, Image, Parcel, PotatoVariety, Ubigeo, User
from app.services.analytics import (
    FieldFilters,
    const,
    current_model,
    dept_code,
    diagnosis_conditions,
    diagnosis_select,
    local_period,
    scoped_parcels_count,
)
from app.services.settings_service import SettingsService

MAX_MAP_POINTS = 5000


def granularity(start: date, end: date) -> str:
    span = (end - start).days
    if span <= 62:
        return "dia"
    if span <= 400:
        return "semana"
    return "mes"


def period_starts(start: date, end: date, gran: str) -> list[date]:
    """Inicios de periodo entre start y end (inclusive), alineados como date_trunc de PostgreSQL."""
    if gran == "dia":
        cur = start
        step = lambda d: d + timedelta(days=1)  # noqa: E731
    elif gran == "semana":
        cur = start - timedelta(days=start.weekday())  # lunes (ISO, igual que date_trunc('week'))
        step = lambda d: d + timedelta(days=7)  # noqa: E731
    else:
        cur = start.replace(day=1)
        step = lambda d: (d.replace(day=28) + timedelta(days=4)).replace(day=1)  # noqa: E731
    out = []
    while cur <= end:
        out.append(cur)
        cur = step(cur)
    return out


def _category_counts():
    return [func.count().filter(Diagnosis.category == c).label(c) for c in CATEGORIES]


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def build(self, user: User, f: FieldFilters) -> dict:
        conds = diagnosis_conditions(user, f)
        kpis = self._kpis(user, f, conds)
        model = current_model(self.db)
        return {
            "alcance": user.role.data_scope,
            "region_usuario": user.region_code,
            "modelo": ({"display_name": model.display_name, "is_demo": model.is_demo, "stage": model.stage}
                       if model else None),
            "kpis": kpis,
            "tendencia": self._trend(f, conds),
            "por_region": self._by_region(conds),
            "por_variedad": self._by_variety(conds),
            **self._map(conds),
        }

    # --- KPIs --------------------------------------------------------------------------------

    def _kpis(self, user: User, f: FieldFilters, conds: list) -> dict:
        row = self.db.execute(diagnosis_select(func.count(), *_category_counts(),
                                               func.count().filter(Diagnosis.status == STATUS_PENDING),
                                               func.count().filter(Image.provenance == "semilla"))
                              .where(*conds)).one()
        total = int(row[0])
        by_cat = [{"categoria": c, "etiqueta": CATEGORY_LABELS[c], "total": int(row[i + 1]),
                   "porcentaje": (row[i + 1] / total) if total else None} for i, c in enumerate(CATEGORIES)]

        days = int(SettingsService(self.db).get("dashboard.dias_casos_recientes"))
        end = f.date_to or today_local()
        recent_conds = diagnosis_conditions(user, f, dates=False) + [
            Diagnosis.category == CATEGORY_TIZON,
            Diagnosis.created_at >= day_start_utc(end - timedelta(days=days - 1)),
            Diagnosis.created_at < day_end_utc(end),
        ]
        recent = self.db.scalar(diagnosis_select(func.count(distinct(Parcel.id))).where(*recent_conds)) or 0

        rev = self.db.execute(
            diagnosis_select(func.count().filter(ExpertReview.decision == "confirma"),
                             func.count().filter(ExpertReview.decision == "corrige"))
            .join(ExpertReview, ExpertReview.diagnosis_id == Diagnosis.id).where(*conds)).one()
        confirms, corrects = int(rev[0]), int(rev[1])
        n = confirms + corrects

        model = current_model(self.db)
        precision = self._model_accuracy(model)
        return {
            "diagnosticos": total,
            "por_categoria": by_cat,
            "pendientes_validacion": int(row[len(CATEGORIES) + 1]),
            "diagnosticos_ejemplo": int(row[len(CATEGORIES) + 2]),
            "parcelas": scoped_parcels_count(self.db, user, f),
            "parcelas_con_casos_compatibles": {"valor": int(recent), "dias": days, "hasta": end.isoformat()},
            "acuerdo_experto": {"valor": (confirms / n) if n else None, "n": n, "confirma": confirms,
                                "corrige": corrects},
            "precision_modelo": precision,
            "alertas_activas": {"valor": None, "motivo": "Disponible con el módulo de riesgo climático (Fase 5)."},
            "parcelas_en_riesgo": {"valor": None,
                                   "motivo": "Disponible con el módulo de riesgo climático (Fase 5)."},
        }

    @staticmethod
    def _model_accuracy(model) -> dict:
        """Accuracy registrada del modelo en producción (validación cruzada; si no hay, validación externa).

        Nunca se muestra para el DEMO ni para un modelo de prueba de humo (D-16, D-40).
        """
        if model is None or model.stage != "production" or model.is_demo or model.smoke_test:
            motivo = ("El modelo en uso es de prueba de humo / no validado: sus métricas no se reportan."
                      if model is not None and model.smoke_test else
                      "No hay un modelo en producción con métricas registradas: el modelo en uso es DEMO / no "
                      "validado. Las métricas llegan al promover un modelo entrenado desde el laboratorio.")
            return {"valor": None, "motivo": motivo, "fuente": None}
        summary = model.metrics_summary or {}
        for key, fuente in (("cv_mean_test_accuracy", "Validación cruzada agrupada (media de las particiones)"),
                            *[(k, "Validación externa (" + k.removeprefix("external_").removesuffix("_accuracy") + ")")
                              for k in sorted(summary) if k.startswith("external_") and k.endswith("_accuracy")],
                            ("val_accuracy", "Validación interna")):
            if summary.get(key) is not None:
                return {"valor": float(summary[key]), "motivo": None, "fuente": fuente}
        return {"valor": None, "motivo": "El modelo en producción no tiene accuracy registrada en MLflow.",
                "fuente": None}

    # --- Tendencia ----------------------------------------------------------------------------

    def _trend(self, f: FieldFilters, conds: list) -> dict:
        end = f.date_to or today_local()
        if f.date_from:
            start = f.date_from
        else:
            first = self.db.scalar(diagnosis_select(func.min(Diagnosis.created_at)).where(*conds))
            start = to_local(first).date() if first else end
        if start > end:
            start = end
        gran = granularity(start, end)
        period = local_period(gran, Diagnosis.created_at)
        rows = self.db.execute(diagnosis_select(period, *_category_counts()).where(*conds)
                               .group_by(period).order_by(period)).all()
        found = {r[0]: r for r in rows}
        series = []
        for p in period_starts(start, end, gran):
            r = found.get(p)
            item = {"periodo": p.isoformat()}
            for i, c in enumerate(CATEGORIES):
                item[c] = int(r[i + 1]) if r else 0
            series.append(item)
        return {"granularidad": gran, "desde": start.isoformat(), "hasta": end.isoformat(), "series": series}

    # --- Distribuciones --------------------------------------------------------------------------

    def _by_region(self, conds: list) -> list[dict]:
        dept = dept_code().label("dept")
        sub = diagnosis_select(dept, *_category_counts(), func.count().label("total")).where(*conds) \
            .group_by(dept).subquery()
        rows = self.db.execute(
            select(sub.c.dept, Ubigeo.name, sub.c.total, *[sub.c[c] for c in CATEGORIES])
            .select_from(sub).outerjoin(Ubigeo, Ubigeo.code == sub.c.dept).order_by(sub.c.total.desc())).all()
        return [{"codigo": r[0], "nombre": r[1] or r[0], "total": int(r[2]),
                 **{c: int(r[3 + i]) for i, c in enumerate(CATEGORIES)}} for r in rows]

    def _by_variety(self, conds: list) -> list[dict]:
        name = func.coalesce(PotatoVariety.name, const("Sin variedad"))
        rows = self.db.execute(
            diagnosis_select(name, func.count(), *_category_counts())
            .outerjoin(PotatoVariety, PotatoVariety.id == Parcel.variety_id).where(*conds)
            .group_by(name).order_by(func.count().desc())).all()
        return [{"nombre": r[0], "total": int(r[1]), **{c: int(r[2 + i]) for i, c in enumerate(CATEGORIES)}}
                for r in rows]

    # --- Mapa de calor ----------------------------------------------------------------------------

    def _map(self, conds: list) -> dict:
        point = func.coalesce(Image.location, Parcel.centroid)
        weight = case((Diagnosis.category == CATEGORY_TIZON, 1.0), (Diagnosis.category == "sospechoso", 0.6),
                      else_=0.2)
        rows = self.db.execute(
            diagnosis_select(func.ST_Y(point), func.ST_X(point), Diagnosis.category, weight,
                             Image.location.is_(None))
            .where(*conds).order_by(Diagnosis.created_at.desc()).limit(MAX_MAP_POINTS + 1)).all()
        return {
            "mapa": [{"lat": float(r[0]), "lon": float(r[1]), "categoria": r[2], "peso": float(r[3]),
                      "aproximado": bool(r[4])} for r in rows[:MAX_MAP_POINTS]],
            "mapa_truncado": len(rows) > MAX_MAP_POINTS,
        }

