"""Carga idempotente de datos semilla.

Uso:  python -m app.seed.seed            (usa MIGRATION_DATABASE_URL)
Los usuarios demo solo se crean si APP_ENV=development y DEMO_USERS_PASSWORD está definido.
La matriz de permisos de los roles del sistema solo se asigna al crear el rol: los cambios hechos
después desde la interfaz se respetan.
"""

import json
import logging
import os

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, now_utc
from app.models import (
    Dataset,
    DifferentialDisease,
    ModelVersion,
    Module,
    Parcel,
    ParcelAssignment,
    Permission,
    PhenologicalStage,
    PotatoVariety,
    Producer,
    Role,
    SystemSetting,
    Ubigeo,
    User,
)
from app.models.security import ACTIONS
from app.seed.data import (
    _SOURCE_DISEASES,
    DATASETS,
    DEMO_MODEL,
    DEMO_USERS,
    DEPARTAMENTOS,
    DISEASES,
    LETTER_TO_ACTION,
    MODULES,
    PARCELS,
    PRODUCERS,
    ROLES,
    STAGES,
    VARIETIES,
)
from app.services.settings_service import SPECS

log = logging.getLogger("papasana.seed")


def seed(db: Session, *, demo_password: str | None, development: bool) -> dict:
    stats = {"modulos": 0, "permisos": 0, "roles": 0, "usuarios": 0, "ubigeo": 0, "parametros": 0}

    # Módulos y permisos (todas las combinaciones módulo × acción de los módulos con permisos)
    modules = {m.code: m for m in db.scalars(select(Module)).all()}
    for order, (code, name, route, phase, req) in enumerate(MODULES, start=1):
        m = modules.get(code)
        if m is None:
            m = Module(code=code, name=name, route=route, sort_order=order, phase=phase, requires_permission=req)
            db.add(m)
            modules[code] = m
            stats["modulos"] += 1
        else:
            m.name, m.route, m.sort_order, m.phase, m.requires_permission = name, route, order, phase, req
    db.flush()

    existing = {(p.module_id, p.action): p for p in db.scalars(select(Permission)).all()}
    perms: dict[str, Permission] = {}
    for m in modules.values():
        if not m.requires_permission:
            continue
        for action in ACTIONS:
            p = existing.get((m.id, action))
            if p is None:
                p = Permission(module_id=m.id, action=action)
                db.add(p)
                stats["permisos"] += 1
            perms[f"{m.code}:{action}"] = p
    db.flush()

    # Roles del sistema
    for code, name, desc, scope, matrix in ROLES:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            role = Role(code=code, name=name, description=desc, data_scope=scope, is_system=True)
            keys = {f"{mod}:{LETTER_TO_ACTION[ch]}" for mod, letters in matrix.items() for ch in letters}
            role.permissions = [perms[k] for k in sorted(keys)]
            db.add(role)
            stats["roles"] += 1
    db.flush()

    # Departamentos
    have = set(db.scalars(select(Ubigeo.code)).all())
    for code, name in DEPARTAMENTOS:
        if code not in have:
            db.add(Ubigeo(code=code, name=name, level="departamento"))
            stats["ubigeo"] += 1

    # Parámetros del sistema
    have = set(db.scalars(select(SystemSetting.key)).all())
    for key, spec in SPECS.items():
        if key not in have:
            db.add(SystemSetting(key=key, value=spec.default, description=spec.description))
            stats["parametros"] += 1
    db.flush()

    # Usuarios demo
    if development and demo_password:
        roles = {r.code: r for r in db.scalars(select(Role)).all()}
        for email, full_name, role_code, institution, region in DEMO_USERS:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(email=email, full_name=full_name, role_id=roles[role_code].id,
                            institution=institution, region_code=region,
                            password_hash=hash_password(demo_password), password_changed_at=now_utc(),
                            preferences={"demo": True}))
                stats["usuarios"] += 1
    db.flush()

    _seed_phase2(db, stats, development=development and bool(demo_password))
    _seed_phase4(db, stats)
    db.commit()
    return stats


def _seed_phase2(db: Session, stats: dict, *, development: bool) -> None:
    stats.update({"variedades": 0, "estadios": 0, "enfermedades": 0, "modelos": 0, "parcelas": 0})
    have = set(db.scalars(select(PotatoVariety.name)).all())
    for name, group in VARIETIES:
        if name not in have:
            db.add(PotatoVariety(name=name, group=group))
            stats["variedades"] += 1
    have = set(db.scalars(select(PhenologicalStage.code)).all())
    for code, name, order, desc in STAGES:
        if code not in have:
            db.add(PhenologicalStage(code=code, name=name, sort_order=order, description=desc))
            stats["estadios"] += 1
    have = set(db.scalars(select(DifferentialDisease.name)).all())
    for name, agent, symptoms, features, target in DISEASES:
        if name not in have:
            db.add(DifferentialDisease(name=name, causal_agent=agent, key_symptoms=symptoms,
                                       distinguishing_features=features, is_target=target,
                                       source=_SOURCE_DISEASES))
            stats["enfermedades"] += 1
    if db.scalar(select(ModelVersion).where(ModelVersion.model_key == DEMO_MODEL["model_key"])) is None:
        db.add(ModelVersion(**DEMO_MODEL))
        stats["modelos"] += 1
    db.flush()

    if not development:
        return
    producers = []
    for name, region in PRODUCERS:
        p = db.scalar(select(Producer).where(Producer.name == name))
        if p is None:
            p = Producer(name=name, region_code=region)
            db.add(p)
            db.flush()
        producers.append(p)
    varieties = {v.name: v.id for v in db.scalars(select(PotatoVariety)).all()}
    stages = {s.code: s.id for s in db.scalars(select(PhenologicalStage)).all()}
    tecnico = db.scalar(select(User).where(User.email == "tecnico@demo.papasana.pe"))
    for code, name, prod_idx, region, variety, stage, alt, geometry, assign in PARCELS:
        if db.scalar(select(Parcel.id).where(Parcel.code == code)):
            continue
        geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
        area = db.scalar(select(func.ST_Area(func.Geography(geom)) / 10000.0))
        parcel = Parcel(code=code, name=name, producer_id=producers[prod_idx].id, region_code=region,
                        variety_id=varieties[variety], phenological_stage_id=stages[stage], altitude_m=alt,
                        geom=geom, centroid=func.ST_Centroid(geom), area_ha=round(float(area), 4),
                        notes="Parcela de ejemplo (datos ficticios).")
        db.add(parcel)
        db.flush()
        if assign and tecnico is not None:
            db.add(ParcelAssignment(parcel_id=parcel.id, user_id=tecnico.id))
        stats["parcelas"] += 1


def _seed_demo_activity(db: Session) -> None:
    """Fase 3: diagnósticos de ejemplo con fotografías sintéticas en MinIO (si MinIO responde)."""
    import time

    from app.core.config import get_settings
    from app.seed.demo_activity import seed_demo_activity
    from app.services.storage_service import get_storage

    storage = get_storage()
    bucket = get_settings().bucket_images
    for attempt in range(10):
        try:
            storage.ensure_bucket(bucket)
            break
        except Exception as e:  # MinIO puede tardar unos segundos en aceptar conexiones
            log.info("MinIO aún no responde (%s); reintento %s/10", type(e).__name__, attempt + 1)
            time.sleep(3)
    else:
        log.warning("Actividad de ejemplo omitida: MinIO no responde. "
                    "Ejecute de nuevo: docker compose run --rm migrate")
        return
    try:
        created = seed_demo_activity(db, storage)
        db.commit()
        log.info("Actividad de ejemplo: %s diagnósticos sintéticos", created)
    except Exception:
        db.rollback()
        log.exception("No se pudo cargar la actividad de ejemplo")


def _seed_phase4(db: Session, stats: dict) -> None:
    """Registro de datasets candidatos (A1). Solo se insertan los que faltan: las verificaciones no se pisan."""
    have = set(db.scalars(select(Dataset.code)).all())
    stats["datasets"] = 0
    for d in DATASETS:
        if d["code"] not in have:
            db.add(Dataset(label_scheme="sintoma", is_active=True, **d))
            stats["datasets"] += 1
    db.flush()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    url = os.environ["MIGRATION_DATABASE_URL"]
    engine = create_engine(url)
    demo_password = os.environ.get("DEMO_USERS_PASSWORD") or None
    development = os.environ.get("APP_ENV", "development") == "development"
    with Session(engine) as db:
        stats = seed(db, demo_password=demo_password, development=development)
        log.info("Datos semilla cargados: %s", stats)
        if development and demo_password and os.environ.get("SEED_DEMO_ACTIVITY", "true").lower() == "true":
            _seed_demo_activity(db)


if __name__ == "__main__":
    main()
