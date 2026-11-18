"""Registra el modelo de un run en el Model Registry de MLflow (`papasana-<arquitectura>`).

Registrar NO pone el modelo en producción: la promoción la propone el Investigador y la aprueba el Administrador
desde el Laboratorio de modelos de la aplicación (cuatro ojos, D-09), que asigna el alias `production`.

Uso:  python -m potato_blight.register --run-id <id> [--description "..."]
"""

import argparse
import json
import logging
import tempfile

import mlflow
from mlflow import MlflowClient

from potato_blight import CLASSES
from potato_blight.mlflow_utils import registered_name, setup
from potato_blight.models.serialize import read_config

log = logging.getLogger("potato_blight")
SUMMARY_KEYS = ("val_macro_f1", "val_mcc", "val_ece", "temperature")


def register_run(run_id: str, description: str | None = None) -> tuple[str, str]:
    client = MlflowClient()
    run = client.get_run(run_id)
    with tempfile.TemporaryDirectory() as tmp:
        local = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model", dst_path=tmp)
        cfg = read_config(local)
    if cfg["classes"] != CLASSES or cfg.get("label_scheme") != "sintoma":
        raise ValueError(f"El modelo debe usar las clases por síntoma {CLASSES} (D-01); tiene {cfg['classes']}.")
    name = registered_name(cfg["architecture"])
    try:
        client.get_registered_model(name)
    except mlflow.exceptions.MlflowException:
        client.create_registered_model(
            name, description=f"Arquitectura {cfg['architecture']} (AP-01, etiquetas por síntoma)")
    tags = {"architecture": cfg["architecture"], "smoke_test": str(cfg.get("smoke_test", False)).lower(),
            "run_type": run.data.tags.get("run_type", ""), "dataset_ids": run.data.tags.get("dataset_ids", ""),
            "label_scheme": "sintoma", "temperature": str(cfg["temperature"]),
            "metrics_summary": json.dumps({k: run.data.metrics[k] for k in run.data.metrics
                                           if k.startswith(("val_", "test_", "external_", "cv_mean_")) or
                                           k in SUMMARY_KEYS}, default=float)[:4900]}
    mv = client.create_model_version(name, source=f"runs:/{run_id}/model", run_id=run_id, tags=tags,
                                     description=description)
    log.info("Registrado %s versión %s (sin alias: la promoción se aprueba en la aplicación)", name, mv.version)
    return name, mv.version


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--experiment", default="papasana-ap01")
    ap.add_argument("--description", default=None)
    args = ap.parse_args(argv)
    setup(args.experiment)
    name, version = register_run(args.run_id, args.description)
    print(json.dumps({"name": name, "version": version}))


if __name__ == "__main__":
    main()

