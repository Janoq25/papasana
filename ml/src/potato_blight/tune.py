"""Búsqueda de hiperparámetros con Optuna (TPE + MedianPruner) y el MISMO presupuesto para los cinco modelos.

El presupuesto (`tuning.n_trials`, `tuning.max_epochs`, `tuning.timeout_hours`) se define en `configs/base.yaml`
y es común a todas las arquitecturas. La búsqueda usa solo el entrenamiento y la validación interna de la
partición `tuning.fold`: la prueba de esa partición NO se evalúa durante la búsqueda.

Uso:  python -m potato_blight.tune --config configs/resnet50.yaml
Escribe los mejores hiperparámetros en configs/tuned/<arquitectura>.yaml.
"""

import argparse
import json
import logging
import time
from pathlib import Path

import mlflow
import optuna
import pandas as pd
import yaml

from potato_blight.config import ExperimentCfg, load_config
from potato_blight.data.splits import fold_split
from potato_blight.mlflow_utils import common_tags, log_json, setup
from potato_blight.train import train_split

log = logging.getLogger("potato_blight")


def search_space(trial: optuna.Trial, arch: str) -> tuple[dict, dict]:
    train = {
        "lr": trial.suggest_float("lr", 1e-5, 3e-3, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
        "label_smoothing": trial.suggest_float("label_smoothing", 0.0, 0.2),
        "batch_size": trial.suggest_categorical("batch_size", [16, 32]),
    }
    hp = {"drop_rate": trial.suggest_float("drop_rate", 0.0, 0.5)}
    if arch == "cnn_vit":
        hp["depth"] = trial.suggest_int("depth", 1, 4)
        hp["d_model"] = trial.suggest_categorical("d_model", [128, 256])
    elif arch == "effnet_att_bilstm":
        hp["hidden"] = trial.suggest_categorical("hidden", [64, 128, 256])
        hp["lstm_layers"] = trial.suggest_int("lstm_layers", 1, 2)
    return train, hp


def tune(cfg: ExperimentCfg, df: pd.DataFrame, storage: str | None = None) -> dict:
    t = cfg.tuning
    parts = fold_split(df, t.fold, cfg.data.n_splits)
    parts = {"train": parts["train"], "val": parts["val"]}  # sin prueba durante la búsqueda
    study = optuna.create_study(
        study_name=f"{cfg.experiment}-{cfg.architecture}", direction="maximize", storage=storage,
        load_if_exists=True, sampler=optuna.samplers.TPESampler(seed=t.seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=3),
    )
    tags = common_tags("tuning", cfg.architecture, smoke_test=cfg.smoke_test,
                       dataset_ids=sorted(set(df["dataset_id"])))
    t0 = time.time()
    with mlflow.start_run(run_name=f"tuning-{cfg.architecture}", tags=tags):
        mlflow.log_params({"n_trials": t.n_trials, "max_epochs": t.max_epochs, "timeout_hours": t.timeout_hours,
                           "fold": t.fold, "sampler": "TPE", "pruner": "MedianPruner"})

        def objective(trial: optuna.Trial) -> float:
            train_over, hp = search_space(trial, cfg.architecture)
            trial_cfg = cfg.model_copy(deep=True)
            trial_cfg.train = trial_cfg.train.model_copy(update=train_over)
            trial_cfg.hparams = {**cfg.hparams, **hp}
            res = train_split(trial_cfg, parts, run_type="tuning_trial", run_name=f"trial-{trial.number}",
                              fold=t.fold, trial=trial, max_epochs=t.max_epochs, log_model=False,
                              evaluate_test=False, nested=True)
            return res.metrics.get("val_macro_f1", 0.0)

        study.optimize(objective, n_trials=t.n_trials, timeout=t.timeout_hours * 3600, gc_after_trial=True)
        hours = (time.time() - t0) / 3600
        states = [tr.state for tr in study.trials]
        summary = {
            "best_value": study.best_value, "best_params": study.best_params, "hours": hours,
            "trials_complete": states.count(optuna.trial.TrialState.COMPLETE),
            "trials_pruned": states.count(optuna.trial.TrialState.PRUNED),
        }
        mlflow.log_metrics({"best_val_macro_f1": study.best_value, "tuning_hours": hours,
                            "trials_complete": summary["trials_complete"], "trials_pruned": summary["trials_pruned"]})
        log_json(summary, "tuning_summary.json")
    return summary


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--storage", default="sqlite:///optuna.db", help="Base de Optuna (permite reanudar)")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    setup(cfg.experiment)
    summary = tune(cfg, pd.read_csv(cfg.data.manifest), args.storage)
    best = summary["best_params"]
    train_keys = {"lr", "weight_decay", "label_smoothing", "batch_size"}
    out = {"base": f"../{Path(args.config).name}",
           "train": {k: v for k, v in best.items() if k in train_keys},
           "hparams": {k: v for k, v in best.items() if k not in train_keys}}
    path = Path(args.config).parent / "tuned" / f"{cfg.architecture}.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.info("Mejores hiperparámetros: %s → %s", json.dumps(best), path)


if __name__ == "__main__":
    main()
