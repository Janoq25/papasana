"""Evalúa el modelo de un run (o de una carpeta local) sobre otro dataset del manifest, sin reentrenar.

Sirve para validaciones externas adicionales (p. ej., un dataset de campo nuevo o las imágenes validadas en la
aplicación). Registra un run `evaluation` con las métricas, la calibración y las predicciones.

Uso:  python -m potato_blight.evaluate --run-id <id> --manifest data/manifest.csv --dataset plantdoc_papa \
          --root plantdoc_papa=data/raw/plantdoc
"""

import argparse
import logging
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from potato_blight.data.dataset import ManifestDataset, eval_transform
from potato_blight.metrics import scalar_metrics
from potato_blight.mlflow_utils import common_tags, log_json, setup
from potato_blight.models.serialize import load_model_dir
from potato_blight.train import _evaluate_split, _predictions_frame

log = logging.getLogger("potato_blight")


def evaluate_model_dir(model_dir: str | Path, df: pd.DataFrame, roots: dict[str, str], batch_size: int = 32):
    model, cfg = load_model_dir(model_dir)
    loader = DataLoader(ManifestDataset(df, roots, eval_transform(cfg["img_size"])), batch_size=batch_size)
    logits, labels = [], []
    with torch.no_grad():
        for x, y, _ in loader:
            logits.append(model(x).numpy())
            labels.append(y.numpy())
    logits, labels = np.concatenate(logits), np.concatenate(labels)
    return cfg, logits, labels


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--root", action="append", required=True, help="dataset_id=carpeta (repetible)")
    ap.add_argument("--experiment", default="papasana-ap01")
    args = ap.parse_args(argv)
    setup(args.experiment)
    roots = dict(r.split("=", 1) for r in args.root)
    df = pd.read_csv(args.manifest)
    df = df[df["dataset_id"] == args.dataset]
    if df.empty:
        raise SystemExit(f"El manifest no tiene imágenes del dataset {args.dataset}")
    with tempfile.TemporaryDirectory() as tmp:
        local = mlflow.artifacts.download_artifacts(run_id=args.run_id, artifact_path="model", dst_path=tmp)
        cfg, logits, labels = evaluate_model_dir(local, df, roots)
    name = f"external_{args.dataset}"
    ev = _evaluate_split(name, logits, labels, cfg["temperature"])
    tags = common_tags("evaluation", cfg["architecture"], smoke_test=cfg.get("smoke_test", False),
                       dataset_ids=[args.dataset])
    tags["evaluated_run_id"] = args.run_id
    with mlflow.start_run(run_name=f"eval-{cfg['architecture']}-{args.dataset}", tags=tags):
        mlflow.log_metrics({**scalar_metrics(ev, name), f"{name}_ece": ev["calibration"]["after"]["ece"]})
        log_json({name: ev}, "evaluation.json")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "predictions.csv"
            _predictions_frame(df, logits, labels, cfg["temperature"], name).to_csv(p, index=False)
            mlflow.log_artifact(str(p))
    log.info("%s: macro-F1 %.3f, MCC %.3f", name, ev["macro_f1"] or 0, ev["mcc"] or 0)


if __name__ == "__main__":
    main()

