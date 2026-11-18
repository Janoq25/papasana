"""Validación por experto (human-in-the-loop). Las etiquetas validadas alimentan futuros reentrenamientos."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.domain.labels import (
    CONFIRMS,
    EVIDENCE_TYPES,
    FINAL_LABELS,
    STATUS_CORRECTED,
    STATUS_PENDING,
    STATUS_VALIDATED,
)
from app.models import DifferentialDisease, ExpertReview, User
from app.services.audit_service import AuditService
from app.services.diagnosis_service import DiagnosisService
from app.services.storage_service import StorageService


class ReviewService:
    def __init__(self, db: Session, storage: StorageService):
        self.db = db
        self.diagnoses = DiagnosisService(db, storage)
        self.audit = AuditService(db)

    def reviews_of(self, diagnosis_id: uuid.UUID) -> list[ExpertReview]:
        return list(self.db.scalars(select(ExpertReview).where(ExpertReview.diagnosis_id == diagnosis_id)
                                    .order_by(ExpertReview.created_at)).all())

    def submit(self, diagnosis_id: uuid.UUID, data: dict[str, Any], reviewer: User, session_id) -> ExpertReview:
        diag = self.diagnoses.get(diagnosis_id, reviewer)
        if diag.status != STATUS_PENDING:
            raise BusinessRuleError("Solo se pueden validar diagnósticos pendientes de revisión.")
        label = data["final_label"]
        if label not in FINAL_LABELS:
            raise BusinessRuleError("Etiqueta final no válida.")
        evidence = data.get("evidence")
        if label == "tizon_tardio_confirmado":
            if evidence not in EVIDENCE_TYPES:
                raise BusinessRuleError("Para confirmar el tizón tardío debe indicar la evidencia (esporulación, "
                                        "laboratorio, cámara húmeda u otra).", code="evidencia_requerida")
            if evidence == "otro" and not (data.get("notes") or "").strip():
                raise BusinessRuleError("Describa la evidencia en las notas.", code="evidencia_requerida")
        elif evidence is not None and evidence not in EVIDENCE_TYPES:
            raise BusinessRuleError("Tipo de evidencia no válido.")
        differential_id = data.get("differential_disease_id")
        if label == "otra_enfermedad":
            if not differential_id or self.db.get(DifferentialDisease, differential_id) is None:
                raise BusinessRuleError("Indique la enfermedad o daño diferencial observado.")
        else:
            differential_id = None

        if label == "no_determinable":
            decision = "no_determinable"
        else:
            decision = "confirma" if label in CONFIRMS.get(diag.category, set()) else "corrige"
        review = ExpertReview(diagnosis_id=diag.id, reviewer_id=reviewer.id, decision=decision, final_label=label,
                              evidence=evidence, differential_disease_id=differential_id,
                              notes=(data.get("notes") or "").strip() or None)
        self.db.add(review)
        before = {"estado": diag.status, "categoria": diag.category}
        diag.status = STATUS_VALIDATED if decision == "confirma" else STATUS_CORRECTED
        self.db.flush()
        self.audit.log(
            "accion", user=reviewer, session_id=session_id, module_code="validacion", action="aprobar",
            entity_type="diagnostico", entity_id=diag.id, before=before,
            after={"estado": diag.status, "decision": decision, "etiqueta_final": label, "evidencia": evidence,
                   "enfermedad_diferencial_id": differential_id, "revision_id": review.id},
        )
        self.db.commit()
        return review
