"""Catálogos: variedades, estadios fenológicos, enfermedades diferenciales y ubigeo."""

import csv
import io
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.models import DifferentialDisease, PhenologicalStage, PotatoVariety, Ubigeo, User
from app.services.audit_service import AuditService, snapshot

CATALOGS: dict[str, type] = {
    "variedades": PotatoVariety,
    "estadios": PhenologicalStage,
    "enfermedades": DifferentialDisease,
}
EDITABLE_FIELDS = {
    "variedades": {"name", "group", "late_blight_susceptibility", "source", "is_active"},
    "estadios": {"name", "code", "sort_order", "description", "is_active"},
    "enfermedades": {"name", "causal_agent", "key_symptoms", "distinguishing_features", "source", "is_active"},
}


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def _model(self, catalog: str):
        model = CATALOGS.get(catalog)
        if model is None:
            raise NotFoundError("Catálogo desconocido.")
        return model

    def list_items(self, catalog: str, include_inactive: bool = False):
        model = self._model(catalog)
        stmt = select(model)
        if not include_inactive:
            stmt = stmt.where(model.is_active.is_(True))
        order = model.sort_order if catalog == "estadios" else model.name
        return list(self.db.scalars(stmt.order_by(order)).all())

    @staticmethod
    def _check_sources(catalog: str, values: dict[str, Any]) -> None:
        """No se registran datos agronómicos (susceptibilidad) sin una fuente verificable."""
        has_source = bool((values.get("source") or "").strip())
        if catalog == "variedades" and values.get("late_blight_susceptibility") and not has_source:
            raise BusinessRuleError("Indique la fuente de la susceptibilidad al tizón tardío.", code="fuente_requerida")

    def create(self, catalog: str, data: dict[str, Any], actor: User, session_id):
        model = self._model(catalog)
        clean = {k: v for k, v in data.items() if k in EDITABLE_FIELDS[catalog]}
        self._check_sources(catalog, clean)
        if self.db.scalar(select(model).where(func.lower(model.name) == clean["name"].strip().lower())):
            raise ConflictError("Ya existe un elemento con ese nombre.")
        obj = model(**clean)
        self.db.add(obj)
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="catalogos", action="crear",
                       entity_type=catalog, entity_id=obj.id, after=snapshot(obj))
        self.db.commit()
        return obj

    def update(self, catalog: str, item_id: int, data: dict[str, Any], actor: User, session_id):
        model = self._model(catalog)
        obj = self.db.get(model, item_id)
        if obj is None:
            raise NotFoundError("Elemento no encontrado.")
        before = snapshot(obj)
        merged = {**before, **{k: v for k, v in data.items() if k in EDITABLE_FIELDS[catalog]}}
        self._check_sources(catalog, merged)
        for k, v in data.items():
            if k in EDITABLE_FIELDS[catalog]:
                setattr(obj, k, v)
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="catalogos", action="editar",
                       entity_type=catalog, entity_id=obj.id, before=before, after=snapshot(obj))
        self.db.commit()
        return obj

    def deactivate(self, catalog: str, item_id: int, actor: User, session_id) -> None:
        """Los elementos de catálogo no se borran (pueden estar referenciados): se desactivan."""
        self.update(catalog, item_id, {"is_active": False}, actor, session_id)

    # --- Ubigeo -----------------------------------------------------------------------------

    def list_ubigeo(self, level: str, parent: str | None, q: str | None):
        stmt = select(Ubigeo).where(Ubigeo.level == level)
        if parent:
            stmt = stmt.where(Ubigeo.parent_code == parent)
        if q:
            stmt = stmt.where(func.lower(Ubigeo.name).like(f"%{q.strip().lower()}%"))
        return list(self.db.scalars(stmt.order_by(Ubigeo.name).limit(500)).all())

    def import_ubigeo(self, raw: bytes, actor: User, session_id) -> dict:
        """Importa provincias y distritos desde un CSV con columnas `ubigeo` y `nombre` (código INEI de 6 dígitos).

        El nivel y el padre se deducen del código: DD0000 departamento, DDPP00 provincia, DDPPdd distrito.
        """
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text), delimiter=";" if text.count(";") > text.count(",") else ",")
        cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
        code_col = cols.get("ubigeo") or cols.get("codigo") or cols.get("code")
        name_col = cols.get("nombre") or cols.get("name") or cols.get("distrito")
        if not code_col or not name_col:
            raise BusinessRuleError("El CSV debe tener las columnas 'ubigeo' y 'nombre'.")
        rows: dict[str, str] = {}
        for r in reader:
            code = (r.get(code_col) or "").strip().zfill(6)
            name = (r.get(name_col) or "").strip()
            if len(code) == 6 and code.isdigit() and name:
                rows[code] = name[:120]
        existing = set(self.db.scalars(select(Ubigeo.code)).all())
        created = 0
        # Ordenar garantiza que el padre exista antes que el hijo
        for code in sorted(rows, key=lambda c: (c[2:] != "0000", c[4:] != "00", c)):
            level, parent = _level_and_parent(code)
            if code in existing:
                continue
            if parent and parent not in existing:
                continue  # sin padre conocido (p. ej. falta el departamento o la provincia)
            self.db.add(Ubigeo(code=code, name=rows[code], level=level, parent_code=parent))
            existing.add(code)
            created += 1
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="catalogos", action="importar",
                       entity_type="ubigeo", after={"filas": len(rows), "creados": created})
        self.db.commit()
        return {"filas_leidas": len(rows), "creados": created}


def _level_and_parent(code: str) -> tuple[str, str | None]:
    if code[2:] == "0000":
        return "departamento", None
    if code[4:] == "00":
        return "provincia", code[:2] + "0000"
    return "distrito", code[:4] + "00"
