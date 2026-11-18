"""Productores y parcelas georreferenciadas (PostGIS), con alcance de datos por rol."""

import json
import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.models import ParcelAssignment, PhenologicalStage, PotatoVariety, Producer, Ubigeo, User
from app.models.field import Parcel
from app.services.audit_service import AuditService, snapshot
from app.services.scope import apply_parcel_scope, parcel_scope_clause

# Límites aproximados del Perú (validación de coordenadas)
PERU_BBOX = (-81.5, -18.5, -68.5, 0.1)  # lon_min, lat_min, lon_max, lat_max
MAX_AREA_HA = 2000.0
PARCEL_FIELDS = ["id", "code", "name", "producer_id", "region_code", "variety_id", "sowing_date",
                 "phenological_stage_id", "altitude_m", "area_ha", "notes", "is_active"]


def _validate_polygon(geojson: dict) -> str:
    if not isinstance(geojson, dict) or geojson.get("type") != "Polygon":
        raise BusinessRuleError("La geometría debe ser un polígono GeoJSON.")
    rings = geojson.get("coordinates") or []
    if not rings or len(rings[0]) < 4:
        raise BusinessRuleError("El polígono necesita al menos 3 vértices.")
    ring = rings[0]
    if ring[0] != ring[-1]:
        ring.append(ring[0])  # cierra el anillo
    lon_min, lat_min, lon_max, lat_max = PERU_BBOX
    for pt in ring:
        if (not isinstance(pt, list | tuple) or len(pt) < 2
                or not (lon_min <= pt[0] <= lon_max and lat_min <= pt[1] <= lat_max)):
            raise BusinessRuleError("Las coordenadas del polígono deben estar dentro del Perú (lon, lat).")
    return json.dumps({"type": "Polygon", "coordinates": [ring]})


def _ubigeo_prefix(code: str) -> str:
    """Prefijo para filtrar por departamento (DD0000), provincia (DDPP00) o distrito."""
    if code.endswith("0000"):
        return code[:2]
    if code.endswith("00"):
        return code[:4]
    return code


class ParcelService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    # --- Consultas ------------------------------------------------------------------------------

    def get(self, parcel_id: int, user: User) -> Parcel:
        parcel = self.db.scalar(apply_parcel_scope(select(Parcel).where(Parcel.id == parcel_id), user))
        if parcel is None:
            raise NotFoundError("Parcela no encontrada o fuera de su alcance.")
        return parcel

    def search(self, user: User, *, q: str | None, region: str | None, variety_id: int | None,
               active: bool | None, page: int, size: int) -> tuple[list[Parcel], int]:
        stmt = apply_parcel_scope(select(Parcel), user)
        if q:
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(func.lower(Parcel.name).like(like) | func.lower(Parcel.code).like(like))
        if region:
            stmt = stmt.where(Parcel.region_code.startswith(_ubigeo_prefix(region)))
        if variety_id:
            stmt = stmt.where(Parcel.variety_id == variety_id)
        if active is not None:
            stmt = stmt.where(Parcel.is_active.is_(active))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = self.db.scalars(stmt.order_by(Parcel.name).offset((page - 1) * size).limit(size)).unique().all()
        return list(items), total

    def geojson(self, user: User, active_only: bool = True) -> dict:
        stmt = select(Parcel.id, Parcel.code, Parcel.name, Parcel.area_ha, Parcel.region_code,
                      func.ST_AsGeoJSON(Parcel.geom, 6))
        clause = parcel_scope_clause(user)
        if clause is not None:
            stmt = stmt.where(clause)
        if active_only:
            stmt = stmt.where(Parcel.is_active.is_(True))
        features = [
            {"type": "Feature", "id": pid, "geometry": json.loads(geom),
             "properties": {"id": pid, "code": code, "name": name, "area_ha": round(area or 0, 3),
                            "region_code": region}}
            for pid, code, name, area, region, geom in self.db.execute(stmt).all()
        ]
        return {"type": "FeatureCollection", "features": features}

    def geometry_of(self, parcel: Parcel) -> tuple[dict, list[float]]:
        geom, centroid = self.db.execute(
            select(func.ST_AsGeoJSON(Parcel.geom, 6), func.ST_AsGeoJSON(Parcel.centroid, 6))
            .where(Parcel.id == parcel.id)
        ).one()
        return json.loads(geom), json.loads(centroid)["coordinates"]

    def assignees(self, parcel_id: int) -> list[uuid.UUID]:
        return list(self.db.scalars(select(ParcelAssignment.user_id).where(ParcelAssignment.parcel_id == parcel_id)))

    # --- Validaciones -----------------------------------------------------------------------

    def _check_refs(self, data: dict[str, Any]) -> None:
        if "region_code" in data and (not data["region_code"] or self.db.get(Ubigeo, data["region_code"]) is None):
            raise BusinessRuleError("La región (ubigeo) no existe.")
        if data.get("variety_id") and self.db.get(PotatoVariety, data["variety_id"]) is None:
            raise BusinessRuleError("La variedad no existe.")
        if data.get("phenological_stage_id") and self.db.get(PhenologicalStage, data["phenological_stage_id"]) is None:
            raise BusinessRuleError("El estadio fenológico no existe.")
        if data.get("producer_id") and self.db.get(Producer, data["producer_id"]) is None:
            raise BusinessRuleError("El productor no existe.")

    def _region_allowed(self, user: User, region_code: str) -> None:
        if user.role.data_scope == "region" and (not user.region_code or region_code[:2] != user.region_code[:2]):
            raise PermissionDeniedError("Solo puede registrar parcelas de su región asignada.")

    def _set_geometry(self, parcel: Parcel, geojson: dict) -> None:
        text = _validate_polygon(geojson)
        valid, area = self.db.execute(select(
            func.ST_IsValid(func.ST_GeomFromGeoJSON(text)),
            func.ST_Area(func.Geography(func.ST_SetSRID(func.ST_GeomFromGeoJSON(text), 4326))) / 10000.0,
        )).one()
        if not valid:
            raise BusinessRuleError("El polígono no es válido (sus lados se cruzan).")
        if area <= 0 or area > MAX_AREA_HA:
            raise BusinessRuleError(f"El área de la parcela debe estar entre 0 y {MAX_AREA_HA:.0f} ha.")
        geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(text), 4326)
        parcel.geom = geom
        parcel.centroid = func.ST_Centroid(geom)
        parcel.area_ha = round(float(area), 4)

    def _next_code(self) -> str:
        n = (self.db.scalar(select(func.count()).select_from(Parcel)) or 0) + 1
        while True:
            code = f"PAR-{n:05d}"
            if self.db.scalar(select(Parcel.id).where(Parcel.code == code)) is None:
                return code
            n += 1

    # --- Escritura ---------------------------------------------------------------------------

    def create(self, data: dict[str, Any], actor: User, session_id) -> Parcel:
        self._check_refs(data)
        self._region_allowed(actor, data["region_code"])
        parcel = Parcel(
            code=data.get("code") or self._next_code(),
            name=data["name"].strip(),
            producer_id=data.get("producer_id"),
            region_code=data["region_code"],
            variety_id=data.get("variety_id"),
            sowing_date=data.get("sowing_date"),
            phenological_stage_id=data.get("phenological_stage_id"),
            altitude_m=data.get("altitude_m"),
            notes=data.get("notes"),
            created_by=actor.id,
        )
        self._set_geometry(parcel, data["geometry"])
        if self.db.scalar(select(Parcel.id).where(Parcel.code == parcel.code)):
            raise BusinessRuleError("Ya existe una parcela con ese código.")
        self.db.add(parcel)
        self.db.flush()
        if actor.role.data_scope == "propio":
            self.db.add(ParcelAssignment(parcel_id=parcel.id, user_id=actor.id))
        self.db.refresh(parcel)
        self.audit.log("accion", user=actor, session_id=session_id, module_code="parcelas", action="crear",
                       entity_type="parcela", entity_id=parcel.id,
                       after=snapshot(parcel, PARCEL_FIELDS) | {"geometria": data["geometry"]})
        self.db.commit()
        return parcel

    def update(self, parcel_id: int, data: dict[str, Any], actor: User, session_id) -> Parcel:
        parcel = self.get(parcel_id, actor)
        before = snapshot(parcel, PARCEL_FIELDS)
        self._check_refs(data)
        if "region_code" in data:
            self._region_allowed(actor, data["region_code"])
        for field in ("name", "producer_id", "region_code", "variety_id", "sowing_date", "phenological_stage_id",
                      "altitude_m", "notes", "is_active"):
            if field in data:
                setattr(parcel, field, data[field])
        if data.get("geometry"):
            before["geometria"] = self.geometry_of(parcel)[0]
            self._set_geometry(parcel, data["geometry"])
        self.db.flush()
        self.db.refresh(parcel)
        after = snapshot(parcel, PARCEL_FIELDS)
        if data.get("geometry"):
            after["geometria"] = data["geometry"]
        self.audit.log("accion", user=actor, session_id=session_id, module_code="parcelas",
                       action="eliminar" if data.get("is_active") is False else "editar",
                       entity_type="parcela", entity_id=parcel.id, before=before, after=after)
        self.db.commit()
        return parcel

    def set_assignments(self, parcel_id: int, user_ids: list[uuid.UUID], actor: User, session_id) -> list[uuid.UUID]:
        parcel = self.get(parcel_id, actor)
        users = self.db.scalars(select(User).where(User.id.in_(user_ids), User.is_active.is_(True))).all()
        if len(users) != len(set(user_ids)):
            raise BusinessRuleError("Algún usuario no existe o está inactivo.")
        before = sorted(str(u) for u in self.assignees(parcel.id))
        self.db.execute(delete(ParcelAssignment).where(ParcelAssignment.parcel_id == parcel.id))
        for uid in set(user_ids):
            self.db.add(ParcelAssignment(parcel_id=parcel.id, user_id=uid))
        self.db.flush()
        after = sorted(str(u) for u in set(user_ids))
        self.audit.log("accion", user=actor, session_id=session_id, module_code="parcelas", action="asignar",
                       entity_type="parcela", entity_id=parcel.id, before={"asignados": before},
                       after={"asignados": after})
        self.db.commit()
        return [uuid.UUID(u) for u in after]

    def assignable_users(self) -> list[User]:
        return list(self.db.scalars(
            select(User).join(User.role).where(User.is_active.is_(True)).order_by(User.full_name)
        ).all())

    # --- Productores --------------------------------------------------------------------------

    def list_producers(self, user: User, q: str | None) -> list[Producer]:
        stmt = select(Producer).where(Producer.is_active.is_(True))
        if user.role.data_scope == "region" and user.region_code:
            stmt = stmt.where(func.left(Producer.region_code, 2) == user.region_code[:2])
        elif user.role.data_scope == "propio":
            stmt = stmt.where(Producer.created_by == user.id)
        if q:
            stmt = stmt.where(func.lower(Producer.name).like(f"%{q.strip().lower()}%"))
        return list(self.db.scalars(stmt.order_by(Producer.name).limit(200)).all())

    def create_producer(self, data: dict[str, Any], actor: User, session_id) -> Producer:
        if data.get("region_code") and self.db.get(Ubigeo, data["region_code"]) is None:
            raise BusinessRuleError("La región (ubigeo) no existe.")
        p = Producer(name=data["name"].strip(), contact=data.get("contact"), region_code=data.get("region_code"),
                     created_by=actor.id)
        self.db.add(p)
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="parcelas", action="crear",
                       entity_type="productor", entity_id=p.id, after=snapshot(p))
        self.db.commit()
        return p
