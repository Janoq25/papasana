"""Actividad de ejemplo para el dashboard y los reportes (solo en desarrollo; docs/decisiones.md D-44).

Genera fotografías SINTÉTICAS (dibujos simples, no hojas reales) y diagnósticos con el modelo DEMO sobre las
parcelas demo, repartidos en los últimos 75 días, y algunas validaciones del especialista demo. Todo queda
marcado con procedencia "semilla" para distinguirlo de los datos reales. Es determinista (semilla fija) e
idempotente: si ya existen imágenes de ejemplo, no hace nada.
"""

import io
import logging
import random
import uuid
from datetime import timedelta

from PIL import Image as PILImage
from PIL import ImageDraw
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import now_utc
from app.domain.images import inspect_image
from app.domain.labels import (
    CATEGORY_SANO,
    CATEGORY_SOSPECHOSO,
    CATEGORY_TIZON,
    STATUS_CORRECTED,
    STATUS_PENDING,
    STATUS_VALIDATED,
    categorize,
)
from app.models import Diagnosis, DifferentialDisease, ExpertReview, Image, ModelVersion, Parcel, User
from app.seed.data import DEMO_MODEL

log = logging.getLogger("papasana")

PROVENANCE = "semilla"
N_DIAGNOSES = 48
SEED = 2026
THRESHOLD = 0.70
CLASSES = ("sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar")
# Peso de cada parcela demo (más actividad en las asignadas al técnico demo)
PARCEL_WEIGHTS = {"DEMO-JUN-001": 0.35, "DEMO-JUN-002": 0.3, "DEMO-JUN-003": 0.2, "DEMO-CUS-001": 0.15}


def synthetic_leaf(rng: random.Random, diseased: bool) -> bytes:
    """Dibujo sintético de una hoja (no es una fotografía): sirve solo para poblar la interfaz."""
    w, h = 320, 240
    img = PILImage.new("RGB", (w, h), (rng.randint(60, 110), rng.randint(90, 130), rng.randint(40, 70)))
    d = ImageDraw.Draw(img)
    cx, cy = rng.randint(120, 200), rng.randint(90, 150)
    rx, ry = rng.randint(80, 120), rng.randint(50, 80)
    leaf = (rng.randint(40, 80), rng.randint(130, 180), rng.randint(40, 70))
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=leaf)
    d.line([cx - rx, cy, cx + rx, cy], fill=(150, 190, 110), width=3)
    for _ in range(rng.randint(3, 8) if diseased else rng.randint(0, 1)):
        x, y = rng.randint(cx - rx + 10, cx + rx - 10), rng.randint(cy - ry + 10, cy + ry - 10)
        r = rng.randint(6, 22)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(rng.randint(70, 110), rng.randint(50, 70), rng.randint(20, 40)))
    for _ in range(400):  # ruido para que cada imagen tenga un hash distinto
        d.point((rng.randrange(w), rng.randrange(h)), fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def _probabilities(rng: random.Random, predicted: str, confidence: float) -> dict[str, float]:
    rest = 1.0 - confidence
    split = rng.uniform(0.2, 0.8)
    others = [c for c in CLASSES if c != predicted]
    return {predicted: round(confidence, 4), others[0]: round(rest * split, 4), others[1]: round(rest * (1 - split), 4)}


def seed_demo_activity(db: Session, storage, *, n: int = N_DIAGNOSES) -> int:
    if db.scalar(select(func.count()).select_from(Image).where(Image.provenance == PROVENANCE)):
        return 0
    model = db.scalar(select(ModelVersion).where(ModelVersion.model_key == DEMO_MODEL["model_key"]))
    parcels = {p.code: p for p in db.scalars(select(Parcel).where(Parcel.code.in_(PARCEL_WEIGHTS))).unique()}
    users = {u.email: u for u in db.scalars(select(User).where(User.email.like("%@demo.papasana.pe"))).unique()}
    tecnico, agronomo, admin = (users.get("tecnico@demo.papasana.pe"), users.get("agronomo@demo.papasana.pe"),
                                users.get("admin@demo.papasana.pe"))
    if model is None or not parcels or tecnico is None or agronomo is None or admin is None:
        log.info("Actividad de ejemplo omitida: faltan el modelo DEMO, las parcelas o los usuarios demo.")
        return 0
    alternaria = db.scalar(select(DifferentialDisease.id).where(DifferentialDisease.name == "Tizón temprano"))
    bounds = {code: db.execute(select(func.ST_XMin(Parcel.geom), func.ST_YMin(Parcel.geom), func.ST_XMax(Parcel.geom),
                                      func.ST_YMax(Parcel.geom)).where(Parcel.id == p.id)).one()
              for code, p in parcels.items()}

    rng = random.Random(SEED)
    bucket = get_settings().bucket_images
    codes = [c for c in PARCEL_WEIGHTS if c in parcels]
    weights = [PARCEL_WEIGHTS[c] for c in codes]
    now = now_utc()
    created = 0
    for i in range(n):
        code = rng.choices(codes, weights)[0]
        parcel = parcels[code]
        uploader = tecnico if code in ("DEMO-JUN-001", "DEMO-JUN-002") else (agronomo if code.startswith("DEMO-JUN")
                                                                              else admin)
        when = now - timedelta(days=rng.uniform(0.2, 75), minutes=rng.randint(0, 600))
        predicted = rng.choices(CLASSES, (0.45, 0.35, 0.2))[0]
        confidence = rng.uniform(0.45, 0.97)
        category, requires_review, status = categorize(predicted, confidence, THRESHOLD)
        raw = synthetic_leaf(rng, diseased=predicted != "sano")
        info = inspect_image(raw)
        xmin, ymin, xmax, ymax = bounds[code]
        lon, lat = rng.uniform(xmin, xmax), rng.uniform(ymin, ymax)

        image_id = uuid.uuid4()
        key = f"semilla/{image_id}.jpg"
        storage.put_bytes(bucket, key, raw, "image/jpeg")
        db.add(Image(
            id=image_id, object_key=key, original_filename=f"ejemplo_sintetico_{i + 1:02d}.jpg", sha256=info.sha256,
            phash=info.phash, mime=info.mime, size_bytes=len(raw), width=info.width, height=info.height, exif={},
            location=func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), gps_source="dispositivo",
            inside_parcel=True, parcel_id=parcel.id, provenance=PROVENANCE, uploaded_by=uploader.id, created_at=when,
        ))
        db.flush()
        diag = Diagnosis(
            image_id=image_id, model_version_id=model.id, predicted_class=predicted, category=category,
            probabilities=_probabilities(rng, predicted, confidence), confidence=round(confidence, 4),
            threshold_used=THRESHOLD, requires_review=requires_review, status=status,
            inference_ms=rng.randint(650, 1450), created_by=uploader.id, created_at=when,
        )
        db.add(diag)
        db.flush()

        # El especialista revisa parte de los casos con más de 3 días en la bandeja
        age_days = (now - when).days
        if status == STATUS_PENDING and age_days > 3 and rng.random() < 0.65 and agronomo is not None:
            if parcel.region_code[:2] != (agronomo.region_code or "")[:2]:
                reviewer = admin  # el agrónomo demo solo ve Junín
            else:
                reviewer = agronomo
            evidence = differential = None
            if category == CATEGORY_TIZON:
                if rng.random() < 0.75:
                    label = "tizon_tardio_confirmado" if rng.random() < 0.4 else "tizon_tardio_sintomas"
                    evidence = "esporulacion" if label == "tizon_tardio_confirmado" else None
                else:
                    label, differential = "otra_enfermedad", alternaria
            elif category == CATEGORY_SOSPECHOSO:
                label = rng.choice(["sano", "tizon_tardio_sintomas", "otra_enfermedad", "no_determinable"])
                differential = alternaria if label == "otra_enfermedad" else None
            else:
                label = "sano"
            confirms = (category == CATEGORY_TIZON and label.startswith("tizon_tardio")) or (
                category == CATEGORY_SANO and label == "sano")
            decision = "no_determinable" if label == "no_determinable" else ("confirma" if confirms else "corrige")
            db.add(ExpertReview(
                diagnosis_id=diag.id, reviewer_id=reviewer.id, decision=decision, final_label=label, evidence=evidence,
                differential_disease_id=differential, notes="Validación de ejemplo (datos sintéticos).",
                created_at=when + timedelta(hours=rng.uniform(2, 70)),
            ))
            diag.status = STATUS_VALIDATED if decision == "confirma" else STATUS_CORRECTED
        created += 1
    db.flush()
    return created
