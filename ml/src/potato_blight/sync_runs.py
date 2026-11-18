"""Copia runs entre servidores de MLflow (p. ej., de Google Colab al MLflow de la aplicación).

En Colab se entrena con un MLflow local guardado en Google Drive (`sqlite:///.../mlflow.db`). Al terminar, en el
equipo donde corre la aplicación:

    python -m potato_blight.sync_runs --origen sqlite:///ruta/a/mlflow.db --destino http://127.0.0.1:5000

Se copian parámetros, el historial completo de métricas, etiquetas (con `source_run_id`), artefactos y la
jerarquía (runs anidados y `cv_parent_run_id`). Los runs ya copiados se omiten (idempotente).
"""

import argparse
import logging
import tempfile

import mlflow
from mlflow import MlflowClient
from mlflow.entities import Metric, Param, RunTag

log = logging.getLogger("potato_blight")
SKIP_TAGS = {"mlflow.parentRunId", "mlflow.rootRunId"}


def _copy_run(src: MlflowClient, dst: MlflowClient, run, exp_id: str, id_map: dict[str, str]) -> str:
    tags = {k: v for k, v in run.data.tags.items() if k not in SKIP_TAGS}
    tags["source_run_id"] = run.info.run_id
    parent = run.data.tags.get("mlflow.parentRunId")
    if parent and parent in id_map:
        tags["mlflow.parentRunId"] = id_map[parent]
    if tags.get("cv_parent_run_id") in id_map:
        tags["cv_parent_run_id"] = id_map[tags["cv_parent_run_id"]]
    new = dst.create_run(exp_id, start_time=run.info.start_time, tags=tags, run_name=run.info.run_name)
    rid = new.info.run_id
    params = [Param(k, v) for k, v in run.data.params.items()]
    metrics = []
    for key in run.data.metrics:
        metrics += [Metric(m.key, m.value, m.timestamp, m.step) for m in src.get_metric_history(run.info.run_id, key)]
    for i in range(0, max(len(params), len(metrics), 1), 500):
        dst.log_batch(rid, metrics=metrics[i:i + 500], params=params[i:i + 100] if i == 0 else [],
                      tags=[RunTag("synced", "true")] if i == 0 else [])
    for p in params[100:]:
        dst.log_param(rid, p.key, p.value)
    with tempfile.TemporaryDirectory() as tmp:
        local = src.download_artifacts(run.info.run_id, "", tmp)
        dst.log_artifacts(rid, local)
    dst.set_terminated(rid, status=run.info.status, end_time=run.info.end_time)
    return rid


def sync(origin: str, destination: str, experiment: str) -> dict:
    src, dst = MlflowClient(origin), MlflowClient(destination)
    exp = src.get_experiment_by_name(experiment)
    if exp is None:
        raise SystemExit(f"El origen no tiene el experimento {experiment}")
    target = dst.get_experiment_by_name(experiment)
    exp_id = target.experiment_id if target else dst.create_experiment(experiment)
    already = {r.data.tags["source_run_id"]: r.info.run_id
               for r in dst.search_runs([exp_id], "tags.source_run_id != ''", max_results=10000)}
    runs = src.search_runs([exp.experiment_id], max_results=10000, order_by=["attributes.start_time ASC"])
    # Padres antes que hijos: primero los runs sin padre
    runs.sort(key=lambda r: (r.data.tags.get("mlflow.parentRunId") is not None, r.info.start_time))
    id_map = dict(already)
    copied = 0
    for run in runs:
        if run.info.run_id in id_map:
            continue
        id_map[run.info.run_id] = _copy_run(src, dst, run, exp_id, id_map)
        copied += 1
        log.info("Copiado %s → %s (%s)", run.info.run_id, id_map[run.info.run_id], run.data.tags.get("run_type"))
    return {"copiados": copied, "omitidos": len(runs) - copied, "experimento": experiment}


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origen", required=True)
    ap.add_argument("--destino", default="http://127.0.0.1:5000")
    ap.add_argument("--experiment", default="papasana-ap01")
    args = ap.parse_args(argv)
    mlflow.set_tracking_uri(args.destino)
    print(sync(args.origen, args.destino, args.experiment))


if __name__ == "__main__":
    main()
