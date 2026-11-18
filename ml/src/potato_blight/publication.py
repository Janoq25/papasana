"""Publica un informe verificable para la app, sin copiar fotos, pesos ni rutas locales.

Desde ml/: python -m potato_blight.publication --source data/comparacion-cuatro
Los informes son snapshots; regenerarlos al terminar un nuevo experimento.
"""
import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import mlflow

from potato_blight.models.architectures import SPECS

HISTORY_KEYS = ("train_loss", "val_loss", "val_macro_f1_epoch", "lr")


def publish(source: Path, destination: Path, manifest: Path = Path("data/manifest.csv")) -> Path:
    result = json.loads((source / "results.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if digest != result["contract"]["manifest_sha256"]:
        raise ValueError("El manifest no coincide con el experimento; no se publica un EDA distinto.")
    with manifest.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    qc = json.loads(manifest.with_suffix(".informe.json").read_text(encoding="utf-8"))
    if (qc["imagenes_originales"] - qc["duplicados_exactos_eliminados"]
            - qc["imagenes_con_etiquetas_en_conflicto"] != len(records)):
        raise ValueError("El informe de calidad no coincide con el número de imágenes del manifest.")
    cfgs = {cfg["architecture"]: cfg for cfg in result["contract"]["configs"]}
    client = mlflow.MlflowClient()
    models, starts = [], []
    for row in result["models"]:
        arch = row["architecture"]
        cfg = cfgs[arch]
        run = client.get_run(row["run_id"])
        if run.info.status != "FINISHED" or run.data.tags.get("excluded_from_comparison") == "true":
            raise ValueError(f"Run no admisible para publicación: {row['run_id']}")
        checkpoint = source / arch / "model/model.pt"
        checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if checkpoint_hash != row["verification"]["checkpoint_sha256"]:
            raise ValueError(f"Checkpoint modificado: {arch}")
        starts.append(run.info.start_time)
        history = {key: [{"step": p.step, "value": p.value} for p in client.get_metric_history(row["run_id"], key)]
                   for key in HISTORY_KEYS}
        models.append({"architecture": arch, "label": SPECS[arch].display_name, "run_id": row["run_id"],
                       "best_epoch": row["best_epoch"], "metrics": row["metrics"], "history": history,
                       "evaluation": row["evaluation"], "checkpoint_sha256": checkpoint_hash,
                       "parameters": row["probe"]["parameters_three_classes"], "checkpoint_mb": row["checkpoint_mb"],
                       "train": cfg["train"], "img_size": cfg["img_size"],
                       "verification": row["verification"]})
    first = cfgs[result["models"][0]["architecture"]]
    development = [r for r in records if r["dataset_id"] in first["data"]["train_datasets"] and int(r["fold"]) >= 0]
    val_fold = result["contract"]["validation_fold"]
    external = [r for r in records if r["dataset_id"] in first["data"]["external_datasets"] and int(r["fold"]) < 0]
    classes = models[0]["evaluation"]["val"]["classes"]
    datasets = []
    for code in sorted({r["dataset_id"] for r in records}):
        sample = [r for r in records if r["dataset_id"] == code]
        counts = Counter(r["label"] for r in sample)
        datasets.append({"id": code, "n": len(sample), "counts": {label: counts[label] for label in classes},
                         "role": "desarrollo" if code in first["data"]["train_datasets"] else "externo"})
    folds = [{"fold": i, "n": sum(int(r["fold"]) == i for r in development),
              "counts": {c: sum(int(r["fold"]) == i and r["label"] == c for r in development) for c in classes}}
             for i in sorted({int(r["fold"]) for r in development})]
    resolution_values = {}
    for dimension in ("width", "height"):
        values = [int(r[dimension]) for r in records]
        q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
        resolution_values[dimension] = [len(values), statistics.mean(values), statistics.stdev(values),
                                        min(values), q1, median, q3, max(values)]
    resolution = [{"metric": label, "width": resolution_values["width"][i],
                   "height": resolution_values["height"][i]} for i, label in enumerate(
                       ["Imágenes", "Media", "Desviación estándar", "Mínimo", "Percentil 25", "Mediana",
                        "Percentil 75", "Máximo"])]
    identifier = re.sub(r"[^a-z0-9_-]", "-", first["experiment"].lower())
    report = {"schema_version": 1, "id": identifier, "title": "Comparación de cuatro modelos · GPU local",
              "trained_on": datetime.fromtimestamp(min(starts) / 1000, UTC).isoformat(),
              "generated_at": datetime.now(UTC).isoformat(), "gpu": result["gpu"], "torch": result["torch"],
              "fingerprint": result["fingerprint"], "manifest_sha256": digest, "classes": classes,
              "data": {"original": qc["imagenes_originales"], "duplicates_removed": qc["duplicados_exactos_eliminados"],
                       "quarantined": qc["imagenes_con_etiquetas_en_conflicto"], "accepted": len(records),
                       "train": sum(int(r["fold"]) != val_fold for r in development),
                       "validation": sum(int(r["fold"]) == val_fold for r in development), "external": len(external),
                       "leaf_groups": len({r["source_group"] for r in development}),
                       "validation_fold": val_fold, "datasets": datasets, "folds": folds, "resolution": resolution},
              "models": models, "selection": result["selection"],
              "limitations": result["limits"] + [
                  "El F1 interno no acredita calidad en campo ni confirmación etiológica.",
                                                "FP16 en ResNet50/EfficientNetV2 y BF16 en MobileNetV4/EfficientViT."],
              "model_sources": json.loads((source / "model_sources.json").read_text(encoding="utf-8")),
              "data_sources": [
                  {"title": "PlantVillage · RGB de papa", "license": "CC-BY-SA-3.0",
                   "url": "https://github.com/spMohanty/PlantVillage-Dataset"},
                  {"title": "PlantDoc · papa", "license": "CC-BY-4.0",
                   "url": "https://github.com/pratikkayal/PlantDoc-Dataset"}]}
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{identifier}.json"
    temporary = target.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/comparacion-cuatro"))
    parser.add_argument("--destination", type=Path, default=Path("../backend/app/data/training_reports"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    args = parser.parse_args()
    print(publish(args.source, args.destination, args.manifest).resolve())


if __name__ == "__main__":
    main()
