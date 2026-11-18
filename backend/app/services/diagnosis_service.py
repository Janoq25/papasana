"""Captura de imágenes y diagnóstico: validación, EXIF/GPS, deduplicación, inferencia, Grad-CAM y lotes."""

import base64
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import BIT
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.security import now_utc
from app.domain.images import ImageInfo, InvalidImageError, inspect_image
from app.domain.labels import STATUS_PENDING, STATUS_VOID, categorize
from app.models import Diagnosis, Image, ModelVersion, Parcel, UploadBatch, User
from app.services.audit_service import AuditService
from app.services.ml_client import MLClient
from app.services.notification_service import NotificationService
from app.services.scope import parcel_scope_clause
from app.services.settings_service import SettingsService
from app.services.storage_service import StorageService

log = logging.getLogger("papasana")


@dataclass
class GpsHint:
    """Ubicación enviada por el cliente cuando la foto no trae GPS en el EXIF."""

    lat: float | None = None
    lon: float | None = None
    source: str = "dispositivo"  # dispositivo | manual


@dataclass
class StoredImage:
    image: Image
    raw: bytes
    info: ImageInfo


def diagnosis_scope_clause(user: User):
    clause = parcel_scope_clause(user)
    if clause is None:
        return None
    return or_(clause, Diagnosis.created_by == user.id)


class DiagnosisService:
    def __init__(self, db: Session, storage: StorageService, ml: MLClient | None = None):
        self.db = db
        self.storage = storage
        self.ml = ml
        self.audit = AuditService(db)
        self.settings = SettingsService(db)
        self.cfg = get_settings()

    # --- Imagen -------------------------------------------------------------------------------

    def _store_image(self, raw: bytes, filename: str | None, parcel: Parcel, user: User, gps: GpsHint | None,
                     batch_id: uuid.UUID | None = None, provenance: str = "web") -> StoredImage:
        if len(raw) > self.cfg.max_image_bytes:
            raise BusinessRuleError(f"La imagen supera {self.cfg.max_image_bytes // (1024 * 1024)} MB.")
        try:
            info = inspect_image(raw)
        except InvalidImageError as e:
            raise BusinessRuleError(str(e), code="imagen_invalida") from e

        exact = self.db.scalar(select(Image).where(Image.parcel_id == parcel.id, Image.sha256 == info.sha256))
        if exact is not None:
            diag_id = self.db.scalar(select(Diagnosis.id).where(Diagnosis.image_id == exact.id)
                                     .order_by(Diagnosis.created_at.desc()))
            raise ConflictError("Esta fotografía ya se subió para esta parcela.", code="imagen_duplicada",
                                detail={"diagnostico_id": str(diag_id) if diag_id else None})

        max_dist = int(self.settings.get("diagnostico.distancia_duplicado"))
        # Distancia de Hamming entre dHash: bit_count(a XOR b) en PostgreSQL
        distance = func.bit_count(cast(Image.phash.op("#")(info.phash), BIT(64)))
        near = self.db.execute(
            select(Image.id, distance).where(distance <= max_dist).order_by(distance).limit(1)
        ).first()

        lat, lon, source = info.lat, info.lon, "exif"
        if lat is None and gps and gps.lat is not None and gps.lon is not None:
            lat, lon, source = gps.lat, gps.lon, gps.source
        if lat is None:
            source = "ninguno"
        point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326) if lat is not None else None
        inside = None
        if point is not None:
            inside = self.db.scalar(select(func.ST_Contains(Parcel.geom, point)).where(Parcel.id == parcel.id))

        image_id = uuid.uuid4()
        now = now_utc()
        key = f"{now:%Y/%m}/{image_id}.{info.extension}"
        self.storage.put_bytes(self.cfg.bucket_images, key, raw, info.mime)
        image = Image(
            id=image_id, object_key=key, original_filename=(filename or "")[:255] or None, sha256=info.sha256,
            phash=info.phash, mime=info.mime, size_bytes=len(raw), width=info.width, height=info.height,
            exif=info.exif, captured_at=info.captured_at, location=point, gps_source=source, inside_parcel=inside,
            parcel_id=parcel.id, batch_id=batch_id, provenance=provenance, uploaded_by=user.id,
            duplicate_of_id=near[0] if near else None, duplicate_distance=int(near[1]) if near else None,
        )
        self.db.add(image)
        self.db.flush()
        return StoredImage(image, raw, info)

    # --- Inferencia ----------------------------------------------------------------------------

    def _model_version(self, model: dict) -> ModelVersion:
        mv = self.db.scalar(select(ModelVersion).where(ModelVersion.model_key == model["key"]))
        if mv is None:
            mlf = model.get("mlflow") or {}
            from_mlflow = model.get("source") == "mlflow"
            mv = ModelVersion(
                model_key=model["key"], architecture=model.get("architecture", "desconocida"),
                display_name=model.get("display_name", model["key"]), is_demo=bool(model.get("is_demo", True)),
                stage="production" if from_mlflow else "demo", classes=model.get("classes", []),
                temperature=float(model.get("temperature", 1.0)), label_scheme="sintoma",
                source="mlflow" if from_mlflow else "demo", mlflow_model_name=mlf.get("name"),
                mlflow_version=mlf.get("version"), mlflow_run_id=mlf.get("run_id"),
                smoke_test=bool(mlf.get("smoke_test", False)),
            )
            self.db.add(mv)
            self.db.flush()
        return mv

    def _infer(self, stored: StoredImage, user: User, session_id) -> Diagnosis:
        assert self.ml is not None
        result = self.ml.predict(stored.raw, stored.image.original_filename or "imagen")
        mv = self._model_version(result["model"])
        threshold = float(self.settings.get("diagnostico.umbral_revision"))
        predicted = result["predicted_class"]
        confidence = float(result["confidence"])
        category, requires_review, status = categorize(predicted, confidence, threshold)
        diag = Diagnosis(
            image_id=stored.image.id, model_version_id=mv.id, predicted_class=predicted, category=category,
            probabilities=result["probabilities"], confidence=confidence, threshold_used=threshold,
            requires_review=requires_review, status=status, inference_ms=result.get("inference_ms"),
            created_by=user.id,
        )
        self.db.add(diag)
        self.db.flush()
        if result.get("gradcam_png_b64"):
            key = f"{now_utc():%Y/%m}/{diag.id}.png"
            self.storage.put_bytes(self.cfg.bucket_gradcam, key, base64.b64decode(result["gradcam_png_b64"]),
                                   "image/png")
            diag.gradcam_key = key
        self.audit.log(
            "accion", user=user, session_id=session_id, module_code="diagnostico", action="diagnosticar",
            entity_type="diagnostico", entity_id=diag.id,
            after={"imagen_id": str(stored.image.id), "parcela_id": stored.image.parcel_id, "categoria": category,
                   "clase_predicha": predicted, "confianza": round(confidence, 4), "umbral": threshold,
                   "requiere_revision": requires_review, "modelo": mv.model_key, "modelo_demo": mv.is_demo,
                   "gps": stored.image.gps_source, "posible_duplicado": stored.image.duplicate_of_id is not None},
        )
        return diag

    def upload_single(self, raw: bytes, filename: str | None, parcel_id: int, user: User, session_id,
                      gps: GpsHint | None = None) -> Diagnosis:
        parcel = self._parcel_for_upload(parcel_id, user)
        stored = self._store_image(raw, filename, parcel, user, gps)
        try:
            diag = self._infer(stored, user, session_id)
        except Exception:
            self.db.rollback()
            self.storage.remove(self.cfg.bucket_images, stored.image.object_key)
            raise
        if diag.status == STATUS_PENDING:
            NotificationService(self.db).notify_pending_review(
                parcel, count=1, uploader=user.id, entity_type="diagnostico", entity_id=diag.id)
        self.db.commit()
        return self.get(diag.id, user)

    def upload_batch(self, files: list[tuple[bytes, str | None]], parcel_id: int, user: User, session_id,
                     gps: GpsHint | None = None) -> tuple[UploadBatch, list[dict]]:
        parcel = self._parcel_for_upload(parcel_id, user)
        max_files = int(self.settings.get("diagnostico.max_imagenes_lote"))
        if not files:
            raise BusinessRuleError("Seleccione al menos una fotografía.")
        if len(files) > max_files:
            raise BusinessRuleError(f"Puede subir como máximo {max_files} fotografías por lote.")
        batch = UploadBatch(user_id=user.id, parcel_id=parcel.id, total=0)
        self.db.add(batch)
        self.db.flush()
        results, accepted = [], []
        for raw, name in files:
            try:
                with self.db.begin_nested():
                    stored = self._store_image(raw, name, parcel, user, gps, batch_id=batch.id)
                accepted.append(stored.image.id)
                results.append({"archivo": name, "aceptada": True, "imagen_id": str(stored.image.id),
                                "posible_duplicado": stored.image.duplicate_of_id is not None})
            except (BusinessRuleError, ConflictError) as e:
                results.append({"archivo": name, "aceptada": False, "motivo": e.message})
        batch.total = len(accepted)
        batch.status = "procesando" if accepted else "completado"
        self.audit.log("accion", user=user, session_id=session_id, module_code="diagnostico", action="subir_lote",
                       entity_type="lote", entity_id=batch.id,
                       after={"parcela_id": parcel.id, "recibidas": len(files), "aceptadas": len(accepted),
                              "rechazadas": len(files) - len(accepted)})
        self.db.commit()
        return batch, results

    def process_batch_image(self, image_id: uuid.UUID, count_failure: bool = True) -> Diagnosis | None:
        """Se ejecuta en el worker de Celery para cada imagen aceptada de un lote.

        `count_failure=False` en los intentos intermedios: el fallo solo se contabiliza en el último reintento.
        """
        image = self.db.get(Image, image_id)
        if image is None or image.batch_id is None:
            return None
        if self.db.scalar(select(Diagnosis.id).where(Diagnosis.image_id == image.id)):
            return None  # idempotente ante reintentos
        user = self.db.get(User, image.uploaded_by)
        raw = self.storage.get_bytes(self.cfg.bucket_images, image.object_key)
        info = inspect_image(raw)
        try:
            diag = self._infer(StoredImage(image, raw, info), user, None)
            self.db.execute(update(UploadBatch).where(UploadBatch.id == image.batch_id)
                            .values(processed=UploadBatch.processed + 1))
        except Exception as e:
            batch_id = image.batch_id
            self.db.rollback()
            # Solo los fallos del servicio de inferencia se reintentan; el resto cuenta como fallo de inmediato.
            if count_failure or not isinstance(e, ServiceUnavailableError):
                self.db.execute(update(UploadBatch).where(UploadBatch.id == batch_id)
                                .values(failed=UploadBatch.failed + 1))
                self._close_batch(batch_id)
                self.db.commit()
            raise
        self._close_batch(image.batch_id)
        self.db.commit()
        return diag

    def _close_batch(self, batch_id: uuid.UUID) -> None:
        closed = self.db.execute(update(UploadBatch).where(
            UploadBatch.id == batch_id, UploadBatch.status != "completado",
            UploadBatch.processed + UploadBatch.failed >= UploadBatch.total,
        ).values(status="completado").returning(UploadBatch.parcel_id, UploadBatch.user_id)).first()
        if closed is None:
            return
        # Una sola notificación por lote para los especialistas (no una por fotografía)
        pending = self.db.scalar(select(func.count()).select_from(Diagnosis).join(Image).where(
            Image.batch_id == batch_id, Diagnosis.status == STATUS_PENDING)) or 0
        parcel = self.db.get(Parcel, closed.parcel_id)
        if parcel is not None:
            NotificationService(self.db).notify_pending_review(
                parcel, count=pending, uploader=closed.user_id, entity_type="lote", entity_id=batch_id)

    def _parcel_for_upload(self, parcel_id: int, user: User) -> Parcel:
        stmt = select(Parcel).where(Parcel.id == parcel_id, Parcel.is_active.is_(True))
        clause = parcel_scope_clause(user)
        if clause is not None:
            stmt = stmt.where(clause)
        parcel = self.db.scalar(stmt)
        if parcel is None:
            raise NotFoundError("Parcela no encontrada, inactiva o fuera de su alcance.")
        return parcel

    # --- Consultas ------------------------------------------------------------------------------

    def _scoped(self, user: User):
        stmt = select(Diagnosis).join(Image, Diagnosis.image_id == Image.id).join(Parcel, Image.parcel_id == Parcel.id)
        clause = diagnosis_scope_clause(user)
        return stmt if clause is None else stmt.where(clause)

    def get(self, diagnosis_id: uuid.UUID, user: User) -> Diagnosis:
        diag = self.db.scalar(self._scoped(user).where(Diagnosis.id == diagnosis_id))
        if diag is None:
            raise NotFoundError("Diagnóstico no encontrado o fuera de su alcance.")
        return diag

    def search(self, user: User, *, status: str | None = None, category: str | None = None,
               parcel_id: int | None = None, requires_review: bool | None = None, date_from=None, date_to=None,
               page: int = 1, size: int = 20, pending_first: bool = False) -> tuple[list[Diagnosis], int]:
        stmt = self._scoped(user)
        if status:
            stmt = stmt.where(Diagnosis.status == status)
        if category:
            stmt = stmt.where(Diagnosis.category == category)
        if parcel_id:
            stmt = stmt.where(Image.parcel_id == parcel_id)
        if requires_review is not None:
            stmt = stmt.where(Diagnosis.requires_review.is_(requires_review))
        if date_from:
            stmt = stmt.where(Diagnosis.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Diagnosis.created_at < date_to)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = ([Diagnosis.requires_review.desc(), Diagnosis.created_at.asc()] if pending_first
                 else [Diagnosis.created_at.desc()])
        items = self.db.scalars(stmt.order_by(*order).offset((page - 1) * size).limit(size)).unique().all()
        return list(items), total

    def batch(self, batch_id: uuid.UUID, user: User) -> tuple[UploadBatch, list[Diagnosis]]:
        batch = self.db.get(UploadBatch, batch_id)
        if batch is None or (batch.user_id != user.id and user.role.data_scope == "propio"):
            raise NotFoundError("Lote no encontrado.")
        diags = self.db.scalars(select(Diagnosis).join(Image).where(Image.batch_id == batch_id)
                                .order_by(Diagnosis.created_at)).unique().all()
        return batch, list(diags)

    def image_bytes(self, diagnosis_id: uuid.UUID, user: User) -> tuple[bytes, str]:
        diag = self.get(diagnosis_id, user)
        return self.storage.get_bytes(self.cfg.bucket_images, diag.image.object_key), diag.image.mime

    def gradcam_bytes(self, diagnosis_id: uuid.UUID, user: User) -> bytes:
        diag = self.get(diagnosis_id, user)
        if not diag.gradcam_key:
            raise NotFoundError("Este diagnóstico no tiene mapa Grad-CAM.")
        return self.storage.get_bytes(self.cfg.bucket_gradcam, diag.gradcam_key)

    def location_of(self, image: Image) -> dict | None:
        if image.location is None:
            return None
        lon, lat = self.db.execute(select(func.ST_X(Image.location), func.ST_Y(Image.location))
                                   .where(Image.id == image.id)).one()
        return {"lat": lat, "lon": lon}

    def void(self, diagnosis_id: uuid.UUID, reason: str, user: User, session_id) -> Diagnosis:
        diag = self.get(diagnosis_id, user)
        if diag.status == STATUS_VOID:
            raise BusinessRuleError("El diagnóstico ya está anulado.")
        before = {"estado": diag.status}
        diag.status = STATUS_VOID
        diag.void_reason = reason.strip()
        self.audit.log("accion", user=user, session_id=session_id, module_code="diagnostico", action="eliminar",
                       entity_type="diagnostico", entity_id=diag.id, before=before,
                       after={"estado": STATUS_VOID, "motivo": diag.void_reason})
        self.db.commit()
        return diag

    def pending_count(self, user: User) -> int:
        stmt = self._scoped(user).where(Diagnosis.status == STATUS_PENDING)
        return self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
