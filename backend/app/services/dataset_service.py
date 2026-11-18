"""Datasets y licencias (módulo A1): ningún dato se usa sin una licencia verificada por una persona.

La verificación registra quién y cuándo revisó la licencia en la fuente oficial. Desde aquí se exporta
`ml/datasets.yaml`, que el pipeline de entrenamiento exige antes de indexar o descargar un dataset.
"""

import re
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.security import now_utc
from app.models import Dataset, ModelVersion, User
from app.services.audit_service import AuditService, snapshot

CLASSES = {"sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"}
EDITABLE = ("name", "version", "source_url", "citation", "conditions", "etiological_confirmation", "has_group_ids",
            "role", "class_map", "n_images", "notes", "is_active")
CODE_RE = re.compile(r"^[a-z0-9_]{3,60}$")


def _check_class_map(class_map: dict) -> None:
    bad = sorted({v for v in class_map.values() if v not in CLASSES})
    if bad:
        raise BusinessRuleError(f"Clases desconocidas en el mapeo: {bad}. Use las clases por síntoma (D-01).")


class DatasetService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def list_all(self) -> list[Dataset]:
        return list(self.db.scalars(select(Dataset).order_by(Dataset.is_active.desc(), Dataset.name)).all())

    def get(self, dataset_id: int) -> Dataset:
        d = self.db.get(Dataset, dataset_id)
        if d is None:
            raise NotFoundError("Dataset no encontrado.")
        return d

    def create(self, data: dict[str, Any], actor: User, session_id) -> Dataset:
        code = data.get("code", "")
        if not CODE_RE.match(code):
            raise BusinessRuleError("El código solo admite minúsculas, números y guion bajo (3 a 60 caracteres).")
        if self.db.scalar(select(Dataset.id).where(Dataset.code == code)):
            raise ConflictError("Ya existe un dataset con ese código.")
        _check_class_map(data.get("class_map") or {})
        d = Dataset(code=code, license_status="por_verificar", label_scheme="sintoma", created_by=actor.id,
                    is_active=True, **{k: data[k] for k in EDITABLE if k in data and k != "is_active"},
                    license=data.get("license"), license_url=data.get("license_url"),
                    license_notes=data.get("license_notes"))
        self.db.add(d)
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="datasets", action="crear",
                       entity_type="dataset", entity_id=d.id, after=snapshot(d))
        self.db.commit()
        return d

    def update(self, dataset_id: int, data: dict[str, Any], actor: User, session_id) -> Dataset:
        d = self.get(dataset_id)
        before = snapshot(d)
        if "class_map" in data:
            _check_class_map(data["class_map"] or {})
        for k in EDITABLE:
            if k in data:
                setattr(d, k, data[k])
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="datasets", action="editar",
                       entity_type="dataset", entity_id=d.id, before=before, after=snapshot(d))
        self.db.commit()
        return d

    def set_license(self, dataset_id: int, data: dict[str, Any], actor: User, session_id) -> Dataset:
        """Registra la revisión de la licencia: quién la verificó, cuándo y con qué fuente."""
        d = self.get(dataset_id)
        before = snapshot(d)
        status = data["license_status"]
        if status == "verificada":
            if not (data.get("license") or "").strip() or not (data.get("license_url") or "").strip():
                raise BusinessRuleError("Para verificar indique la licencia y el enlace a la fuente oficial donde la "
                                        "revisó.", code="licencia_incompleta")
        if status in ("verificada", "rechazada") and not (data.get("license_notes") or "").strip():
            raise BusinessRuleError("Describa la revisión (qué fuente consultó y qué permite la licencia).",
                                    code="licencia_incompleta")
        d.license_status = status
        d.license = (data.get("license") or "").strip() or d.license
        d.license_url = (data.get("license_url") or "").strip() or d.license_url
        d.license_notes = (data.get("license_notes") or "").strip() or d.license_notes
        if status == "por_verificar":
            d.license_verified_by, d.license_verified_at = None, None
        else:
            d.license_verified_by, d.license_verified_at = actor.id, now_utc()
        self.db.flush()
        self.audit.log("accion", user=actor, session_id=session_id, module_code="datasets", action="verificar_licencia",
                       entity_type="dataset", entity_id=d.id, before=before, after=snapshot(d))
        self.db.commit()
        return d

    def delete(self, dataset_id: int, actor: User, session_id) -> None:
        d = self.get(dataset_id)
        used = [m.model_key for m in self.db.scalars(select(ModelVersion)).all()
                if d.code in (m.train_dataset_ids or [])]
        if used:
            raise ConflictError("El dataset está asociado a versiones de modelo: desactívelo en lugar de borrarlo.",
                                detail={"modelos": used})
        before = snapshot(d)
        self.db.delete(d)
        self.audit.log("accion", user=actor, session_id=session_id, module_code="datasets", action="eliminar",
                       entity_type="dataset", entity_id=dataset_id, before=before)
        self.db.commit()

    def export_yaml(self, actor: User, session_id) -> str:
        """Genera `ml/datasets.yaml` con el estado de licencias registrado en la aplicación."""
        users = {u.id: u for u in self.db.scalars(select(User)).unique().all()}
        items = []
        for d in self.list_all():
            if not d.is_active:
                continue
            v = users.get(d.license_verified_by)
            generated = d.conditions == "sintetico" and d.license_status == "verificada"
            items.append({
                "id": d.code, "name": d.name, "version": d.version, "source_url": d.source_url, "license": d.license,
                "license_url": d.license_url, "license_status": d.license_status,
                "license_verified_by": (f"{v.full_name} <{v.email}>" if v else
                                        ("generado por potato_blight.data.synthetic" if generated else None)),
                "license_verified_at": d.license_verified_at.date().isoformat() if d.license_verified_at else None,
                "license_notes": d.license_notes, "citation": d.citation, "conditions": d.conditions,
                "label_scheme": d.label_scheme,
                "etiological_confirmation": {"no": False, "si": True}.get(d.etiological_confirmation,
                                                                          d.etiological_confirmation),
                "has_group_ids": d.has_group_ids, "role": d.role, "class_map": d.class_map, "notes": d.notes,
            })
        header = ("# Generado desde la aplicación (módulo Datasets y licencias) el "
                  f"{now_utc().date().isoformat()}. No edite license_status a mano: regístrelo en la aplicación.\n")
        self.audit.log("accion", user=actor, session_id=session_id, module_code="datasets", action="exportar",
                       entity_type="registro_datasets", after={"datasets": len(items)})
        self.db.commit()
        return header + yaml.safe_dump({"datasets": items}, allow_unicode=True, sort_keys=False, width=110)
