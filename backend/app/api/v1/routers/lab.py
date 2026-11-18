from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, require_any_permission, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.lab import DecisionIn, LabModelOut, PromotionIn, PromotionOut
from app.services.lab_service import LabService
from app.services.ml_client import MLClient, get_ml_client
from app.services.mlflow_client import MLflowClient, get_mlflow_client

router = APIRouter(prefix="/laboratorio", tags=["Laboratorio de modelos"])


def _svc(db: Session = Depends(get_db), mlflow: MLflowClient = Depends(get_mlflow_client),
         ml: MLClient = Depends(get_ml_client)) -> LabService:
    return LabService(db, mlflow, ml)


def _promotion_out(db: Session, p) -> PromotionOut:
    out = PromotionOut.model_validate(p)
    names = dict(db.execute(select(User.id, User.full_name).where(
        User.id.in_([x for x in (p.requested_by, p.decided_by) if x]))).all())
    out.requested_by_name = names.get(p.requested_by)
    out.decided_by_name = names.get(p.decided_by) if p.decided_by else None
    return out


@router.get("/modelos", response_model=list[LabModelOut], summary="Versiones de modelo (DEMO y registradas)")
def list_models(_: CurrentUser = Depends(require_permission("laboratorio", "ver")), svc: LabService = Depends(_svc)):
    return svc.models()


@router.post("/sincronizar", summary="Sincronizar las versiones con el Model Registry de MLflow")
def sync(current: CurrentUser = Depends(require_any_permission(("laboratorio", "crear"), ("laboratorio", "aprobar"))),
         svc: LabService = Depends(_svc)):
    return svc.sync(current.user, current.session.id)


@router.get("/modelos/{model_id}", summary="Detalle: parámetros, métricas, curvas, calibración y entrenamiento")
def model_detail(model_id: int, _: CurrentUser = Depends(require_permission("laboratorio", "ver")),
                 svc: LabService = Depends(_svc)):
    d = svc.detail(model_id)
    return {**d, "modelo": LabModelOut.model_validate(d["modelo"])}


@router.get("/comparacion", summary="Última comparación estadística entre modelos (Friedman, Wilcoxon-Holm, …)")
def comparison(_: CurrentUser = Depends(require_permission("laboratorio", "ver")), svc: LabService = Depends(_svc)):
    return svc.comparison()


@router.get("/estado", summary="Estado de MLflow y del modelo cargado en ml-service")
def status(_: CurrentUser = Depends(require_permission("laboratorio", "ver")), svc: LabService = Depends(_svc)):
    return svc.status()


@router.get("/promociones", response_model=list[PromotionOut], summary="Historial de promociones y rollbacks")
def promotions(_: CurrentUser = Depends(require_permission("laboratorio", "ver")), svc: LabService = Depends(_svc),
               db: Session = Depends(get_db)):
    return [_promotion_out(db, p) for p in svc.promotions()]


@router.post("/promociones", response_model=PromotionOut, status_code=201,
             summary="Solicitar la promoción a producción o un rollback (la aprueba otra persona)")
def request_promotion(body: PromotionIn, current: CurrentUser = Depends(require_permission("laboratorio", "crear")),
                      svc: LabService = Depends(_svc), db: Session = Depends(get_db)):
    p = svc.request(current.user, current.session.id, body.model_version_id, body.action, body.reason)
    return _promotion_out(db, p)


@router.post("/promociones/{promotion_id}/aprobar", response_model=PromotionOut,
             summary="Aprobar y aplicar (mueve el alias production y recarga ml-service)")
def approve(promotion_id: int, body: DecisionIn,
            current: CurrentUser = Depends(require_permission("laboratorio", "aprobar")),
            svc: LabService = Depends(_svc), db: Session = Depends(get_db)):
    return _promotion_out(db, svc.approve(current.user, current.session.id, promotion_id, body.reason))


@router.post("/promociones/{promotion_id}/rechazar", response_model=PromotionOut,
             summary="Rechazar (quien aprueba) o cancelar (quien solicitó)")
def reject(promotion_id: int, body: DecisionIn,
           current: CurrentUser = Depends(require_any_permission(("laboratorio", "aprobar"), ("laboratorio", "crear"))),
           svc: LabService = Depends(_svc), db: Session = Depends(get_db)):
    return _promotion_out(db, svc.reject(current.user, current.session.id, promotion_id, body.reason or ""))
