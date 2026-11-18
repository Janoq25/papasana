"""Cliente mínimo de la API REST de MLflow (Model Registry y artefactos), sin instalar MLflow.

ml-service solo necesita: encontrar la versión con alias `production` entre los modelos `papasana-*` y
descargar su carpeta `model/` (model.pt + model_config.json) a una caché local.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

log = logging.getLogger("ml-service")
PREFIX = "papasana-"
ALIAS = "production"


@dataclass(frozen=True)
class ProductionModel:
    name: str
    version: str
    run_id: str
    source: str


class RegistryError(RuntimeError):
    pass


class RegistryClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=timeout)

    def _get(self, endpoint: str, params: dict) -> dict:
        r = self.http.get(endpoint, params=params)
        if r.status_code == 404:
            return {}
        if r.status_code >= 400:
            raise RegistryError(f"MLflow respondió {r.status_code} en {endpoint}: {r.text[:200]}")
        return r.json()

    def production_model(self) -> ProductionModel | None:
        """La versión con alias `production` entre los modelos `papasana-*` (si hay varias, la más reciente)."""
        data = self._get("/api/2.0/mlflow/registered-models/search",
                         {"filter": f"name LIKE '{PREFIX}%'", "max_results": 100})
        candidates = []
        for rm in data.get("registered_models", []):
            for a in rm.get("aliases", []):
                if a.get("alias") == ALIAS:
                    candidates.append((int(rm.get("last_updated_timestamp", 0)), rm["name"], str(a["version"])))
        if not candidates:
            return None
        if len(candidates) > 1:
            log.warning("Hay %s modelos con alias production; se usa el actualizado más recientemente",
                        len(candidates))
        _, name, version = max(candidates)
        mv = self._get("/api/2.0/mlflow/model-versions/get", {"name": name, "version": version}).get("model_version")
        if not mv:
            raise RegistryError(f"No se encontró {name} v{version} en el registro")
        return ProductionModel(name, version, mv.get("run_id", ""), mv.get("source", ""))

    def _list(self, run_id: str, path: str) -> list[dict]:
        return self._get("/api/2.0/mlflow/artifacts/list", {"run_id": run_id, "path": path}).get("files", [])

    def download_model_dir(self, pm: ProductionModel, dest: Path) -> Path:
        """Descarga `runs:/<run>/model` (artefactos servidos por el propio servidor de MLflow)."""
        if not pm.run_id:
            raise RegistryError("La versión no está asociada a un run (source sin run_id)")
        files = [f for f in self._list(pm.run_id, "model") if not f.get("is_dir")]
        if not files:
            raise RegistryError(f"El run {pm.run_id} no tiene la carpeta model/")
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            name = Path(f["path"]).name
            with self.http.stream("GET", "/get-artifact", params={"run_id": pm.run_id, "path": f["path"]}) as r:
                if r.status_code >= 400:
                    raise RegistryError(f"No se pudo descargar {f['path']}: HTTP {r.status_code}")
                tmp = dest / f".{name}.part"
                with tmp.open("wb") as fh:
                    for chunk in r.iter_bytes():
                        fh.write(chunk)
                tmp.replace(dest / name)
        return dest
