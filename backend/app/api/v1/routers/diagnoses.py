import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, require_permission
from app.api.v1.field_serializers import diagnosis_out
from app.core.config import get_settings
from app.core.errors import BusinessRuleError
from app.db.session import get_db
from app.domain.labels import CATEGORY_LABELS, EVIDENCE_TYPES, FINAL_LABELS, STATUS_PENDING
from app.models import ModelVersion
from app.schemas.common import Page
from app.schemas.field import BatchOut, DiagnosisOut, ModelVersionOut, ReviewIn, VoidIn
from app.services.diagnosis_service import DiagnosisService, GpsHint
from app.services.ml_client import MLClient, get_ml_client
from app.services.review_service import ReviewService
from app.services.storage_service import StorageService, get_storage
from app.workers.tasks import process_image

router = APIRouter(tags=["Captura y diagnóstico"])


async def _read_limited(file: UploadFile) -> bytes:
    limit = get_settings().max_image_bytes
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise BusinessRuleError(f"«{file.filename}» supera {limit // (1024 * 1024)} MB.")
    return raw


def _gps(lat: float | None, lon: float | None, source: str | None) -> GpsHint | None:
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise BusinessRuleError("Coordenadas inválidas.")
    return GpsHint(lat=lat, lon=lon, source="manual" if source == "manual" else "dispositivo")


@router.get("/diagnosticos/etiquetas", summary="Categorías, etiquetas finales y tipos de evidencia (D-01)")
def labels(_: CurrentUser = Depends(require_permission("diagnostico", "ver"))):
    return {"categorias": CATEGORY_LABELS, "etiquetas_finales": FINAL_LABELS, "evidencias": EVIDENCE_TYPES}


@router.get("/modelos/activo", response_model=ModelVersionOut | None, summary="Modelo en uso por ml-service")
def active_model(_: CurrentUser = Depends(require_permission("diagnostico", "ver")), db: Session = Depends(get_db),
                 ml: MLClient = Depends(get_ml_client)):
    info = ml.model_info()
    return db.scalar(select(ModelVersion).where(ModelVersion.model_key == info["key"]))


@router.post("/diagnosticos", response_model=DiagnosisOut, status_code=201,
             summary="Subir una fotografía y diagnosticarla (síncrono)")
async def upload_one(
    file: UploadFile = File(...),
    parcel_id: int = Form(...),
    lat: float | None = Form(default=None),
    lon: float | None = Form(default=None),
    gps_source: str | None = Form(default=None),
    current: CurrentUser = Depends(require_permission("diagnostico", "crear")),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
    ml: MLClient = Depends(get_ml_client),
):
    raw = await _read_limited(file)
    gps = _gps(lat, lon, gps_source)

    def work():
        svc = DiagnosisService(db, storage, ml)
        diag = svc.upload_single(raw, file.filename, parcel_id, current.user, current.session.id, gps)
        return diagnosis_out(db, diag, storage)

    # La inferencia y la base de datos son bloqueantes: se ejecutan fuera del bucle de eventos.
    return await run_in_threadpool(work)


@router.post("/diagnosticos/lote", response_model=BatchOut, status_code=202,
             summary="Subir varias fotografías (se procesan en segundo plano)")
async def upload_batch(
    files: list[UploadFile] = File(...),
    parcel_id: int = Form(...),
    lat: float | None = Form(default=None),
    lon: float | None = Form(default=None),
    gps_source: str | None = Form(default=None),
    current: CurrentUser = Depends(require_permission("diagnostico", "crear")),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    payload = [(await _read_limited(f), f.filename) for f in files[:51]]
    gps = _gps(lat, lon, gps_source)
    batch, results = await run_in_threadpool(
        DiagnosisService(db, storage).upload_batch, payload, parcel_id, current.user, current.session.id, gps)
    for r in results:
        if r["aceptada"]:
            process_image.delay(r["imagen_id"])
    return BatchOut(id=batch.id, status=batch.status, total=batch.total, processed=batch.processed,
                    failed=batch.failed, created_at=batch.created_at, results=results)


@router.get("/diagnosticos/lotes/{batch_id}", response_model=BatchOut, summary="Estado de un lote")
def get_batch(batch_id: uuid.UUID, current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
              db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    batch, diags = DiagnosisService(db, storage).batch(batch_id, current.user)
    return BatchOut(id=batch.id, status=batch.status, total=batch.total, processed=batch.processed,
                    failed=batch.failed, created_at=batch.created_at,
                    diagnoses=[diagnosis_out(db, d, storage, with_reviews=False) for d in diags])


@router.get("/diagnosticos", response_model=Page[DiagnosisOut], summary="Historial de diagnósticos (según alcance)")
def list_diagnoses(
    status: str | None = Query(default=None, max_length=25),
    category: str | None = Query(default=None, max_length=30),
    parcel_id: int | None = None,
    requires_review: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    items, total = DiagnosisService(db, storage).search(
        current.user, status=status, category=category, parcel_id=parcel_id, requires_review=requires_review,
        date_from=date_from, date_to=date_to, page=page, size=size)
    return Page[DiagnosisOut](items=[diagnosis_out(db, d, storage, with_reviews=False) for d in items],
                              total=total, page=page, size=size)


@router.get("/diagnosticos/{diagnosis_id}", response_model=DiagnosisOut, summary="Detalle del diagnóstico")
def get_diagnosis(diagnosis_id: uuid.UUID, current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
                  db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    return diagnosis_out(db, DiagnosisService(db, storage).get(diagnosis_id, current.user), storage)


@router.get("/diagnosticos/{diagnosis_id}/imagen", response_class=Response, summary="Fotografía original")
def get_image(diagnosis_id: uuid.UUID, current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
              db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    data, mime = DiagnosisService(db, storage).image_bytes(diagnosis_id, current.user)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "private, max-age=600"})


@router.get("/diagnosticos/{diagnosis_id}/gradcam", response_class=Response, summary="Superposición Grad-CAM")
def get_gradcam(diagnosis_id: uuid.UUID, current: CurrentUser = Depends(require_permission("diagnostico", "ver")),
                db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    data = DiagnosisService(db, storage).gradcam_bytes(diagnosis_id, current.user)
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.post("/diagnosticos/{diagnosis_id}/anular", response_model=DiagnosisOut, summary="Anular con motivo")
def void_diagnosis(diagnosis_id: uuid.UUID, body: VoidIn,
                   current: CurrentUser = Depends(require_permission("diagnostico", "eliminar")),
                   db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    diag = DiagnosisService(db, storage).void(diagnosis_id, body.reason, current.user, current.session.id)
    return diagnosis_out(db, diag, storage)


# --- Validación por experto ----------------------------------------------------------------------

@router.get("/validacion/pendientes", response_model=Page[DiagnosisOut], tags=["Validación por experto"],
            summary="Bandeja de casos pendientes (primero los que requieren revisión)")
def pending(page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100),
            current: CurrentUser = Depends(require_permission("validacion", "ver")),
            db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    items, total = DiagnosisService(db, storage).search(current.user, status=STATUS_PENDING, page=page, size=size,
                                                        pending_first=True)
    return Page[DiagnosisOut](items=[diagnosis_out(db, d, storage, with_reviews=False) for d in items],
                              total=total, page=page, size=size)


@router.post("/diagnosticos/{diagnosis_id}/revision", response_model=DiagnosisOut, tags=["Validación por experto"],
             summary="Confirmar o corregir la etiqueta (especialista)")
def review(diagnosis_id: uuid.UUID, body: ReviewIn,
           current: CurrentUser = Depends(require_permission("validacion", "aprobar")),
           db: Session = Depends(get_db), storage: StorageService = Depends(get_storage)):
    ReviewService(db, storage).submit(diagnosis_id, body.model_dump(), current.user, current.session.id)
    return diagnosis_out(db, DiagnosisService(db, storage).get(diagnosis_id, current.user), storage)
