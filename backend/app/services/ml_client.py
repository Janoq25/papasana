"""Cliente HTTP del servicio de inferencia (ml-service, red interna de Docker)."""

import logging

import httpx

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

log = logging.getLogger("papasana")


class MLClient:
    def __init__(self, base_url: str, token: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Internal-Token": token} if token else {}
        self.timeout = timeout

    def predict(self, raw: bytes, filename: str) -> dict:
        try:
            r = httpx.post(f"{self.base_url}/predict", files={"file": (filename or "imagen", raw)},
                           headers=self.headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            log.warning("ml-service no disponible: %s", e)
            raise ServiceUnavailableError("El servicio de inferencia no está disponible. Intente más tarde.") from e
        if r.status_code != 200:
            log.warning("ml-service respondió %s: %s", r.status_code, r.text[:300])
            raise ServiceUnavailableError("El servicio de inferencia no pudo procesar la imagen.")
        return r.json()

    def model_info(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/model", headers=self.headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            raise ServiceUnavailableError("El servicio de inferencia no está disponible.") from e

    def reload(self) -> dict:
        """Pide a ml-service que vuelva a resolver el alias `production` (tras una promoción o un rollback)."""
        try:
            r = httpx.post(f"{self.base_url}/reload", headers=self.headers, timeout=max(self.timeout, 120))
        except httpx.HTTPError as e:
            raise ServiceUnavailableError("El servicio de inferencia no está disponible.") from e
        if r.status_code != 200:
            detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else ""
            raise ServiceUnavailableError(f"ml-service no pudo cargar el modelo: {detail or r.status_code}")
        return r.json()


def get_ml_client() -> MLClient:
    s = get_settings()
    return MLClient(s.ml_service_url, s.ml_service_token, s.ml_timeout_seconds)
