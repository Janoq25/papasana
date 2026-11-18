"""ml-service: inferencia y Grad-CAM. Solo accesible en la red interna de Docker (sin puerto publicado)."""

import hmac
import io
import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.model import LoadResult, Predictor, load_predictor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ml-service")

MAX_BYTES = 15 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000
_state: dict = {}
_reload_lock = threading.Lock()


def _install(result: LoadResult) -> None:
    _state["predictor"] = result.predictor
    _state["status"] = {"estado": result.status, "detalle": result.detail,
                        "cargado_en": datetime.now(UTC).isoformat()}


@asynccontextmanager
async def lifespan(_: FastAPI):
    _install(load_predictor())
    log.info("Modelo cargado: %s (%s)", _state["predictor"].info.key, _state["status"]["estado"])
    yield


app = FastAPI(title="PapaSana ml-service", version="0.4.0", lifespan=lifespan, docs_url=None, redoc_url=None)


def check_token(x_internal_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("ML_SERVICE_TOKEN", "")
    if expected and not hmac.compare_digest(expected, x_internal_token or ""):
        raise HTTPException(status_code=401, detail="Token interno inválido")


def predictor() -> Predictor:
    return _state["predictor"]


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": "predictor" in _state}


@app.get("/model", dependencies=[Depends(check_token)])
def model_info(p: Predictor = Depends(predictor)):
    return {**p.info.as_dict(), "load_status": _state.get("status")}


@app.post("/reload", dependencies=[Depends(check_token)])
def reload_model():
    """Vuelve a resolver el alias `production` en MLflow (lo llama el backend al aprobar una promoción).

    Si el modelo de producción no se puede cargar, se conserva el modelo actual y se responde 503: el backend
    revierte el alias y marca la promoción como fallida.
    """
    with _reload_lock:
        try:
            result = load_predictor(fallback_to_demo=False)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"No se pudo cargar el modelo: {e}"[:500]) from e
        _install(result)
    log.info("Modelo recargado: %s (%s)", result.predictor.info.key, result.status)
    return {**result.predictor.info.as_dict(), "load_status": _state["status"]}


@app.post("/predict", dependencies=[Depends(check_token)])
def predict(file: UploadFile = File(...), p: Predictor = Depends(predictor)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Imagen demasiado grande")
    try:
        Image.open(io.BytesIO(raw)).verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise HTTPException(status_code=422, detail="Imagen inválida") from e
    return p.predict(raw)
