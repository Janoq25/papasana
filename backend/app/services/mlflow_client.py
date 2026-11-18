"""Cliente de la API REST de MLflow para el Laboratorio de modelos (sin instalar MLflow en el backend).

Endpoints verificados contra MLflow 3.18 (docs/decisiones.md D-52). Particularidades:
- borrar un alias exige el cuerpo JSON en el DELETE (los parámetros en la URL se ignoran);
- el servidor valida la cabecera Host (`--allowed-hosts`).
"""

import json
import logging
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

log = logging.getLogger("papasana")
PREFIX = "papasana-"
PRODUCTION_ALIAS = "production"


class MLflowClient:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base)

    def _request(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None,
                 allow_404: bool = False):
        if not self.base:
            raise ServiceUnavailableError("MLflow no está configurado (MLFLOW_TRACKING_URI).")
        try:
            r = httpx.request(method, f"{self.base}{path}", params=params, json=body, timeout=self.timeout)
        except httpx.HTTPError as e:
            raise ServiceUnavailableError("MLflow no está disponible en este momento.") from e
        if allow_404 and (r.status_code == 404 or (r.status_code == 400 and "not found" in r.text.lower())):
            return None
        if r.status_code >= 400:
            log.warning("MLflow %s %s → %s %s", method, path, r.status_code, r.text[:300])
            raise ServiceUnavailableError(f"MLflow rechazó la operación ({r.status_code}).")
        return r

    def health(self) -> bool:
        try:
            return self._request("GET", "/health").status_code == 200
        except ServiceUnavailableError:
            return False

    # --- Registro de modelos ----------------------------------------------------------------------

    def registered_models(self) -> list[dict]:
        r = self._request("GET", "/api/2.0/mlflow/registered-models/search",
                          params={"filter": f"name LIKE '{PREFIX}%'", "max_results": 100})
        return r.json().get("registered_models", [])

    def model_versions(self, name: str) -> list[dict]:
        r = self._request("GET", "/api/2.0/mlflow/model-versions/search",
                          params={"filter": f"name='{name}'", "max_results": 200})
        return r.json().get("model_versions", [])

    def set_alias(self, name: str, version: str, alias: str = PRODUCTION_ALIAS) -> None:
        self._request("POST", "/api/2.0/mlflow/registered-models/alias",
                      body={"name": name, "alias": alias, "version": str(version)})

    def delete_alias(self, name: str, alias: str = PRODUCTION_ALIAS) -> None:
        self._request("DELETE", "/api/2.0/mlflow/registered-models/alias", body={"name": name, "alias": alias},
                      allow_404=True)

    def alias_holders(self, alias: str = PRODUCTION_ALIAS) -> list[tuple[str, str]]:
        """(modelo, versión) que tienen el alias, entre los modelos `papasana-*`."""
        out = []
        for rm in self.registered_models():
            for a in rm.get("aliases") or []:
                if a.get("alias") == alias:
                    out.append((rm["name"], str(a["version"])))
        return out

    # --- Runs y artefactos ----------------------------------------------------------------------------

    def get_run(self, run_id: str) -> dict | None:
        r = self._request("GET", "/api/2.0/mlflow/runs/get", params={"run_id": run_id}, allow_404=True)
        if r is None:
            return None
        run = r.json()["run"]
        data = run.get("data", {})
        return {
            "info": run.get("info", {}),
            "metrics": {m["key"]: m["value"] for m in data.get("metrics", [])},
            "params": {p["key"]: p["value"] for p in data.get("params", [])},
            "tags": {t["key"]: t["value"] for t in data.get("tags", [])},
        }

    def metric_history(self, run_id: str, key: str) -> list[dict]:
        r = self._request("GET", "/api/2.0/mlflow/metrics/get-history",
                          params={"run_id": run_id, "metric_key": key}, allow_404=True)
        if r is None:
            return []
        return sorted(({"step": m.get("step", 0), "value": m["value"]} for m in r.json().get("metrics", [])),
                      key=lambda m: m["step"])

    def artifact_json(self, run_id: str, path: str) -> dict | list | None:
        r = self._request("GET", "/get-artifact", params={"run_id": run_id, "path": path}, allow_404=True)
        if r is None:
            return None
        try:
            return json.loads(r.content)
        except ValueError:
            return None

    def experiment_id(self, name: str) -> str | None:
        r = self._request("GET", "/api/2.0/mlflow/experiments/get-by-name", params={"experiment_name": name},
                          allow_404=True)
        return r.json()["experiment"]["experiment_id"] if r is not None else None

    def search_runs(self, experiment: str, filter_string: str, max_results: int = 20) -> list[dict]:
        eid = self.experiment_id(experiment)
        if eid is None:
            return []
        r = self._request("POST", "/api/2.0/mlflow/runs/search",
                          body={"experiment_ids": [eid], "filter": filter_string, "max_results": max_results,
                                "order_by": ["attributes.start_time DESC"]})
        return r.json().get("runs", [])


@lru_cache
def _client(base: str) -> MLflowClient:
    return MLflowClient(base)


def get_mlflow_client() -> MLflowClient:
    return _client(get_settings().mlflow_tracking_uri)
