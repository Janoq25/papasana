"""Serialización de parcelas y diagnósticos (requieren consultas adicionales: geometría, revisiones)."""

from sqlalchemy.orm import Session

from app.domain.labels import CATEGORY_LABELS, FINAL_LABELS
from app.models import Diagnosis, Parcel
from app.schemas.field import (
    CatalogItemOut,
    DiagnosisOut,
    ImageOut,
    ModelVersionOut,
    ParcelOut,
    ProducerOut,
    ReviewOut,
)
from app.services.diagnosis_service import DiagnosisService
from app.services.parcel_service import ParcelService
from app.services.review_service import ReviewService
from app.services.settings_service import SettingsService


def parcel_out(db: Session, p: Parcel, with_geometry: bool = True) -> ParcelOut:
    svc = ParcelService(db)
    geometry, centroid = svc.geometry_of(p) if with_geometry else (None, None)
    return ParcelOut(
        id=p.id, code=p.code, name=p.name, region_code=p.region_code,
        producer=ProducerOut.model_validate(p.producer) if p.producer else None,
        variety=CatalogItemOut.model_validate(p.variety) if p.variety else None,
        stage=CatalogItemOut.model_validate(p.stage) if p.stage else None,
        sowing_date=p.sowing_date, altitude_m=p.altitude_m, area_ha=p.area_ha, notes=p.notes, is_active=p.is_active,
        geometry=geometry, centroid=centroid, assignees=svc.assignees(p.id), created_at=p.created_at,
    )


def diagnosis_out(db: Session, d: Diagnosis, storage, with_reviews: bool = True) -> DiagnosisOut:
    svc = DiagnosisService(db, storage)
    img = d.image
    reviews = ReviewService(db, storage).reviews_of(d.id) if with_reviews else []
    return DiagnosisOut(
        id=d.id, created_at=d.created_at, status=d.status, category=d.category,
        category_label=CATEGORY_LABELS.get(d.category, d.category), predicted_class=d.predicted_class,
        probabilities=d.probabilities, confidence=d.confidence, threshold_used=d.threshold_used,
        requires_review=d.requires_review, has_gradcam=bool(d.gradcam_key), inference_ms=d.inference_ms,
        void_reason=d.void_reason, model=ModelVersionOut.model_validate(d.model_version),
        parcel={"id": img.parcel.id, "code": img.parcel.code, "name": img.parcel.name,
                "region_code": img.parcel.region_code},
        image=ImageOut(
            id=img.id, original_filename=img.original_filename, width=img.width, height=img.height,
            size_bytes=img.size_bytes, captured_at=img.captured_at, gps_source=img.gps_source,
            location=svc.location_of(img), inside_parcel=img.inside_parcel, exif=img.exif or {},
            provenance=img.provenance, duplicate_of_id=img.duplicate_of_id,
            duplicate_distance=img.duplicate_distance,
        ),
        reviews=[
            ReviewOut(id=r.id, reviewer_id=r.reviewer_id, decision=r.decision, final_label=r.final_label,
                      final_label_name=FINAL_LABELS.get(r.final_label, r.final_label), evidence=r.evidence,
                      differential=r.differential.name if r.differential else None, notes=r.notes,
                      created_at=r.created_at)
            for r in reviews
        ],
        created_by=d.created_by,
        disclaimer=str(SettingsService(db).get("aviso.supervision_profesional")),
    )
