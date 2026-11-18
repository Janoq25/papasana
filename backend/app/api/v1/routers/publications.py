"""Resultados para el artículo: mismo permiso de lectura del Laboratorio."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, require_permission
from app.services.publication_service import list_reports, read_report

router = APIRouter(prefix="/laboratorio/publicaciones", tags=["Resultados para el artículo"])
can_read = require_permission("laboratorio", "ver")


class ReportSummary(BaseModel):
    id: str
    title: str
    trained_on: str
    model_count: int


@router.get("", response_model=list[ReportSummary], summary="Informes científicos publicados desde entrenamientos")
def index(_: CurrentUser = Depends(can_read)):
    return list_reports()


@router.get("/{identifier}", summary="EDA, métricas, curvas, parámetros y trazabilidad del informe")
def detail(identifier: str, _: CurrentUser = Depends(can_read)):
    return read_report(identifier)
