"""Laboratorio de modelos (M07): registro, métricas, comparación y promoción/rollback con cuatro ojos (D-09).

- El Model Registry de MLflow es la fuente de verdad: `sync()` copia sus versiones a `ml.model_versions`.
- El modelo en uso es el que tiene el alias `production`. Promover o hacer rollback = mover ese alias y pedir a
  ml-service que recargue. Si la recarga falla, el alias vuelve a su estado anterior y la promoción queda
  `fallida` (el servicio nunca queda sin modelo).
- Cuatro ojos: quien solicita (laboratorio:crear) no puede aprobar su propia solicitud (laboratorio:aprobar).
- No se muestra ninguna métrica que no venga de un run registrado (el DEMO no tiene métricas, D-16).
"""

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from app.models import ModelPromotion, ModelVersion, User
from app.services.audit_service import AuditService
from app.services.ml_client import MLClient
from app.services.mlflow_client import PREFIX, MLflowClient
from app.services.notification_service import NotificationService

log = logging.getLogger("papasana")

ARCH_NAMES = {
    "resnet50": "ResNet50", "efficientnet_b3": "EfficientNet-B3", "convnext_tiny": "ConvNeXt-Tiny",
    "cnn_vit": "H1 · CNN-ViT híbrido", "effnet_att_bilstm": "H2 · EfficientNet-Atención-BiLSTM",
}
SUMMARY_PREFIXES = ("val_", "test_", "external_", "cv_mean_", "cv_std_")
HISTORY_KEYS = ("train_loss", "val_loss", "val_macro_f1_epoch")
APPROVE_PERMISSION = "laboratorio:aprobar"


def _now() -> datetime:
    return datetime.now(UTC)


def display_name(arch: str, name: str, version: str, smoke: bool) -> str:
    label = f"{ARCH_NAMES.get(arch, arch)} · {name} v{version}"
    return f"SMOKE TEST / no validado · {label}" if smoke else label


class LabService:
    def __init__(self, db: Session, mlflow: MLflowClient, ml: MLClient | None = None):
        self.db = db
        self.mlflow = mlflow
        self.ml = ml
        self.audit = AuditService(db)
        self.cfg = get_settings()

    # --- Sincronización con el Model Registry ---------------------------------------------------------

    def sync(self, user: User | None = None, session_id=None) -> dict:
        holders = set(self.mlflow.alias_holders())
        seen, created, updated = set(), 0, 0
        for rm in self.mlflow.registered_models():
            name = rm["name"]
            if not name.startswith(PREFIX):
                continue
            for v in self.mlflow.model_versions(name):
                version = str(v["version"])
                key = f"{name}:v{version}"
                seen.add(key)
                tags = {t["key"]: t["value"] for t in v.get("tags", [])}
                arch = tags.get("architecture") or name.removeprefix(PREFIX).replace("-", "_")
                smoke = tags.get("smoke_test", "false") == "true"
                try:
                    summary = json.loads(tags.get("metrics_summary") or "{}")
                except ValueError:
                    summary = {}
                if not summary and v.get("run_id"):
                    run = self.mlflow.get_run(v["run_id"]) or {}
                    summary = {k: val for k, val in run.get("metrics", {}).items() if k.startswith(SUMMARY_PREFIXES)}
                mv = self.db.scalar(select(ModelVersion).where(ModelVersion.model_key == key))
                if mv is None:
                    mv = ModelVersion(model_key=key, label_scheme="sintoma",
                                      classes=["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"])
                    self.db.add(mv)
                    created += 1
                else:
                    updated += 1
                mv.architecture = arch
                mv.display_name = display_name(arch, name, version, smoke)
                mv.source, mv.is_demo, mv.smoke_test = "mlflow", smoke, smoke
                mv.mlflow_model_name, mv.mlflow_version, mv.mlflow_run_id = name, version, v.get("run_id")
                mv.temperature = float(tags.get("temperature") or 1.0)
                mv.train_dataset_ids = [d for d in (tags.get("dataset_ids") or "").split(",") if d]
                mv.metrics_summary = summary or None
                mv.registered_at = datetime.fromtimestamp(int(v.get("creation_timestamp", 0)) / 1000, UTC)
                mv.synced_at = _now()
                if (name, version) in holders:
                    mv.stage = "production"
                elif mv.stage == "production":
                    mv.stage = "archived"  # perdió el alias fuera de la aplicación
                elif mv.stage != "archived":
                    mv.stage = "staging"   # registrada, candidata a promoción
        # El DEMO queda en "demo"; si ninguna versión tiene el alias, el DEMO es el modelo en uso.
        self.db.flush()
        out = {"creados": created, "actualizados": updated, "en_produccion": sorted(f"{n}:v{v}" for n, v in holders)}
        if user is not None:
            self.audit.log("accion", user=user, session_id=session_id, module_code="laboratorio",
                           action="sincronizar", entity_type="registro_mlflow", after=out)
        self.db.commit()
        return out

    # --- Consultas ------------------------------------------------------------------------------------

    def models(self) -> list[ModelVersion]:
        order = {"production": 0, "staging": 1, "demo": 2, "archived": 3}
        rows = list(self.db.scalars(select(ModelVersion)).all())
        return sorted(rows, key=lambda m: (order.get(m.stage, 9), -m.id))

    def get(self, model_id: int) -> ModelVersion:
        mv = self.db.get(ModelVersion, model_id)
        if mv is None:
            raise NotFoundError("Versión de modelo no encontrada.")
        return mv

    def detail(self, model_id: int) -> dict:
        mv = self.get(model_id)
        out = {"modelo": mv, "run": None, "evaluacion": None, "historial": {}, "validacion_cruzada": None,
               "mlflow_url": None}
        if mv.source != "mlflow" or not mv.mlflow_run_id:
            out["mensaje"] = "Modelo DEMO sin entrenar: no tiene métricas (D-16)."
            return out
        run = self.mlflow.get_run(mv.mlflow_run_id)
        if run is None:
            out["mensaje"] = "El run asociado ya no existe en MLflow."
            return out
        out["run"] = {"params": run["params"], "metrics": run["metrics"],
                      "tags": {k: v for k, v in run["tags"].items() if not k.startswith("mlflow.")}}
        out["evaluacion"] = self.mlflow.artifact_json(mv.mlflow_run_id, "evaluation.json")
        out["historial"] = {k: self.mlflow.metric_history(mv.mlflow_run_id, k) for k in HISTORY_KEYS}
        parent = run["tags"].get("cv_parent_run_id")
        if parent:
            prun = self.mlflow.get_run(parent)
            if prun:
                out["validacion_cruzada"] = {"run_id": parent, "metrics": {
                    k: v for k, v in prun["metrics"].items() if k.startswith(("cv_mean_", "cv_std_"))}}
        exp_id = run["info"].get("experiment_id")
        if exp_id:
            out["mlflow_url"] = f"{self.cfg.mlflow_ui_url.rstrip('/')}/#/experiments/{exp_id}/runs/{mv.mlflow_run_id}"
        return out

    def comparison(self) -> dict:
        """Última comparación estadística registrada (`potato_blight.compare`). Sin runs reales: se declara."""
        runs = self.mlflow.search_runs(self.cfg.mlflow_experiment, "tags.run_type = 'comparison'", 20)
        if not runs:
            return {"estado": "sin_experimentos",
                    "mensaje": "Sin experimentos registrados: ejecute potato_blight.compare después de la "
                               "validación cruzada de los modelos (docs/guia_entrenamiento.md)."}
        real = [r for r in runs if _tag(r, "smoke_test") != "true"]
        chosen = (real or runs)[0]
        data = self.mlflow.artifact_json(chosen["info"]["run_id"], "comparison.json") or {}
        return {**data, "run_id": chosen["info"]["run_id"], "solo_prueba_de_humo": not real,
                "registrado_en": chosen["info"].get("start_time")}

    def status(self) -> dict:
        ml = None
        if self.ml is not None:
            try:
                ml = self.ml.model_info()
            except ServiceUnavailableError as e:
                ml = {"error": e.message}
        prod = self.db.scalar(select(ModelVersion).where(ModelVersion.stage == "production"))
        return {"mlflow_configurado": self.mlflow.configured, "mlflow_disponible": self.mlflow.health(),
                "mlflow_url": self.cfg.mlflow_ui_url, "ml_service": ml,
                "produccion_registrada": prod.model_key if prod else None}

    # --- Promociones (cuatro ojos) ----------------------------------------------------------------------

    def promotions(self) -> list[ModelPromotion]:
        return list(self.db.scalars(select(ModelPromotion).order_by(ModelPromotion.created_at.desc(),
                                                                    ModelPromotion.id.desc()).limit(100)).all())

    def current_production(self) -> ModelVersion | None:
        return self.db.scalar(select(ModelVersion).where(ModelVersion.stage == "production"))

    def demo_version(self) -> ModelVersion | None:
        return self.db.scalar(select(ModelVersion).where(ModelVersion.source == "demo").order_by(ModelVersion.id))

    def request(self, user: User, session_id, model_id: int, action: str, reason: str) -> ModelPromotion:
        reason = (reason or "").strip()
        if len(reason) < 10:
            raise BusinessRuleError("Explique el motivo de la solicitud (al menos 10 caracteres).")
        if action not in ("promover", "rollback"):
            raise BusinessRuleError("Acción no válida: use 'promover' o 'rollback'.")
        target = self.get(model_id)
        if self.db.scalar(select(ModelPromotion.id).where(ModelPromotion.status == "pendiente")):
            raise ConflictError("Ya hay una solicitud pendiente: debe aprobarse o rechazarse antes de crear otra.",
                                code="promocion_pendiente")
        current = self.current_production()
        if target.stage == "production" or (target.source == "demo" and current is None):
            raise BusinessRuleError("Esta versión ya es la que está en uso.")
        if action == "promover" and target.source != "mlflow":
            raise BusinessRuleError("Solo se promueven versiones registradas en MLflow.")
        if action == "rollback":
            was_prod = target.source == "demo" or self.db.scalar(select(ModelPromotion.id).where(
                ModelPromotion.status == "aplicada", ModelPromotion.previous_model_version_id == target.id))
            if not was_prod:
                raise BusinessRuleError("El rollback solo puede volver a una versión que estuvo en producción "
                                        "o al modelo DEMO.")
        promo = ModelPromotion(model_version_id=target.id, action=action, status="pendiente",
                               from_stage=target.stage, to_stage="production",
                               previous_model_version_id=current.id if current else None,
                               requested_by=user.id, request_reason=reason)
        self.db.add(promo)
        self.db.flush()
        self.audit.log("accion", user=user, session_id=session_id, module_code="laboratorio", action="crear",
                       entity_type="promocion_modelo", entity_id=promo.id,
                       after={"accion": action, "modelo": target.model_key, "smoke_test": target.smoke_test,
                              "actual": current.model_key if current else None, "motivo": reason})
        notifier = NotificationService(self.db)
        verb = "Promoción" if action == "promover" else "Rollback"
        for approver in self.db.scalars(select(User).where(User.is_active.is_(True))).unique():
            if approver.id != user.id and APPROVE_PERMISSION in approver.role.permission_keys:
                notifier.notify(approver.id, "aprobacion_modelo", f"{verb} de modelo por aprobar",
                                f"{target.display_name} · solicitado por {user.full_name}", "/laboratorio",
                                "promocion_modelo", promo.id)
        self.db.commit()
        return promo

    def _pending(self, promotion_id: int) -> ModelPromotion:
        promo = self.db.get(ModelPromotion, promotion_id)
        if promo is None:
            raise NotFoundError("Solicitud no encontrada.")
        if promo.status != "pendiente":
            raise BusinessRuleError(f"La solicitud ya está {promo.status}.")
        return promo

    def _decide(self, promo: ModelPromotion, user: User, status: str, reason: str | None, error: str | None = None):
        promo.status, promo.decided_by, promo.decided_at = status, user.id, _now()
        promo.decision_reason = (reason or "").strip() or None
        promo.error = error

    def approve(self, user: User, session_id, promotion_id: int, reason: str | None) -> ModelPromotion:
        promo = self._pending(promotion_id)
        if promo.requested_by == user.id:
            self.audit.log("acceso_denegado", user=user, session_id=session_id, module_code="laboratorio",
                           action="aprobar", entity_type="promocion_modelo", entity_id=promo.id, result="fallo",
                           error_detail="cuatro ojos: el solicitante no puede aprobar su propia solicitud")
            self.db.commit()
            raise PermissionDeniedError("Principio de cuatro ojos: otra persona debe aprobar esta solicitud.",
                                        code="cuatro_ojos")
        if self.ml is None:
            raise ServiceUnavailableError("El servicio de inferencia no está configurado.")
        target = promo.model_version
        before_holders = self.mlflow.alias_holders()
        previous = self.current_production()
        try:
            for name, _ in before_holders:  # un solo modelo con alias production en todo el registro
                if name != target.mlflow_model_name:
                    self.mlflow.delete_alias(name)
            # Rollback al DEMO: basta con que ningún modelo tenga el alias (ml-service sirve el DEMO)
            if target.source == "mlflow":
                self.mlflow.set_alias(target.mlflow_model_name, target.mlflow_version)
            loaded = self.ml.reload()
            if loaded.get("key") != target.model_key:
                raise ServiceUnavailableError(
                    f"ml-service cargó {loaded.get('key')} en lugar de {target.model_key}.")
        except ServiceUnavailableError as e:
            self._restore_aliases(before_holders)
            self._decide(promo, user, "fallida", reason, e.message)
            self.audit.log("accion", user=user, session_id=session_id, module_code="laboratorio", action="aprobar",
                           entity_type="promocion_modelo", entity_id=promo.id, result="fallo",
                           error_detail=e.message, after={"modelo": target.model_key, "estado": "fallida"})
            self.db.commit()
            raise
        if previous is not None and previous.id != target.id:
            previous.stage = "archived" if previous.source == "mlflow" else "demo"
        target.stage = "production" if target.source == "mlflow" else "demo"
        promo.previous_model_version_id = previous.id if previous else None
        self._decide(promo, user, "aplicada", reason)
        self.audit.log("accion", user=user, session_id=session_id, module_code="laboratorio", action="aprobar",
                       entity_type="promocion_modelo", entity_id=promo.id,
                       before={"en_uso": previous.model_key if previous else "demo"},
                       after={"en_uso": target.model_key, "accion": promo.action, "smoke_test": target.smoke_test,
                              "solicitado_por": str(promo.requested_by), "motivo": promo.decision_reason})
        NotificationService(self.db).notify(
            promo.requested_by, "aprobacion_modelo", f"Solicitud aplicada: {target.display_name}",
            f"Aprobada por {user.full_name}", "/laboratorio", "promocion_modelo", promo.id)
        self.db.commit()
        return promo

    def _restore_aliases(self, holders: list[tuple[str, str]]) -> None:
        try:
            current = set(self.mlflow.alias_holders())
            for name, _ in current - set(holders):
                self.mlflow.delete_alias(name)
            for name, version in holders:
                self.mlflow.set_alias(name, version)
            self.ml.reload()
        except ServiceUnavailableError:
            log.exception("No se pudo restaurar el alias production tras una promoción fallida")

    def reject(self, user: User, session_id, promotion_id: int, reason: str) -> ModelPromotion:
        promo = self._pending(promotion_id)
        if not (reason or "").strip():
            raise BusinessRuleError("Indique el motivo del rechazo.")
        own = promo.requested_by == user.id
        if own:
            self._decide(promo, user, "cancelada", reason)
        else:
            if APPROVE_PERMISSION not in user.role.permission_keys:
                raise PermissionDeniedError("Solo quien aprueba puede rechazar; el solicitante puede cancelar.")
            self._decide(promo, user, "rechazada", reason)
        self.audit.log("accion", user=user, session_id=session_id, module_code="laboratorio",
                       action="cancelar" if own else "rechazar", entity_type="promocion_modelo", entity_id=promo.id,
                       after={"estado": promo.status, "motivo": reason})
        if not own:
            NotificationService(self.db).notify(
                promo.requested_by, "aprobacion_modelo", f"Solicitud rechazada: {promo.model_version.display_name}",
                reason, "/laboratorio", "promocion_modelo", promo.id)
        self.db.commit()
        return promo


def _tag(run: dict, key: str) -> str | None:
    for t in run.get("data", {}).get("tags", []):
        if t["key"] == key:
            return t["value"]
    return None
