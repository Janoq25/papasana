"""Compara el ajuste previo con fine-tuning progresivo y entrena un candidato local.

La elección usa únicamente validación interna. PlantDoc se evalúa una vez, al final.
Es un piloto de una partición; no sustituye la comparación anidada de cinco modelos.
"""

import argparse
import json
import logging
import shutil
from pathlib import Path

import mlflow
import pandas as pd
import torch

from potato_blight.config import load_config
from potato_blight.data.splits import fold_split
from potato_blight.mlflow_utils import setup
from potato_blight.train import run_final, train_split


def run(config: str, output: Path) -> dict:
    cfg = load_config(config)
    if not torch.cuda.is_available():
        raise RuntimeError("El piloto solicitado requiere CUDA; no se ejecuta en CPU.")
    setup(cfg.experiment)
    df = pd.read_csv(cfg.data.manifest)
    parts = fold_split(df, 0, cfg.data.n_splits)
    baseline = cfg.model_copy(deep=True)
    baseline.train = baseline.train.model_copy(update={"lr": 3e-4, "label_smoothing": 0.0,
                                                      "freeze_epochs": 0, "backbone_lr_factor": 1.0})
    # El test interno tampoco se consulta durante la selección del perfil.
    development = {"train": parts["train"], "val": parts["val"]}
    results = {}
    for name, candidate in (("referencia", baseline), ("progresivo", cfg)):
        result = train_split(candidate, development, run_type="pilot", run_name=f"piloto-{name}")
        mlflow.MlflowClient().set_tag(result.run_id, "validation_protocol", "pilot_single_split")
        results[name] = {"run_id": result.run_id, "metrics": result.metrics, "best_epoch": result.best_epoch}
    selected = max(results, key=lambda name: results[name]["metrics"]["val_macro_f1"])
    selected_cfg = cfg if selected == "progresivo" else baseline
    # Después de elegir el perfil, entrenamos con todos los grupos salvo la validación interna.
    final = run_final(selected_cfg, df, val_fold=1)
    mlflow.MlflowClient().set_tag(final.run_id, "validation_protocol", "pilot_candidate_not_publication")
    output.mkdir(parents=True, exist_ok=True)
    downloaded = mlflow.artifacts.download_artifacts(run_id=final.run_id, artifact_path="model")
    shutil.copytree(downloaded, output / "model", dirs_exist_ok=True)
    summary = {"gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
               "profiles": results, "selected_by": "val_macro_f1", "selected_profile": selected,
               "final_run_id": final.run_id, "final_metrics": final.metrics,
               "limitations": ["Piloto de una partición, sin validación anidada completa.",
                               "PlantDoc no participó en la selección de hiperparámetros.",
                               "Candidato entrenado, sin promoción automática a la aplicación."]}
    (output / "resultados.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "config_seleccionada.json").write_text(selected_cfg.model_dump_json(indent=2), encoding="utf-8")
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/resnet50_laptop.yaml")
    parser.add_argument("--output", type=Path, default=Path("data/piloto-resnet50"))
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
