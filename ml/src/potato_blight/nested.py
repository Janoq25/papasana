"""Validación agrupada anidada: búsqueda nueva en cada fold externo, sin usar PlantDoc.

Uso: python -m potato_blight.nested --config configs/resnet50_laptop.yaml
Los folds externos estiman el procedimiento de selección. PlantDoc queda reservado para la evaluación final.
"""

import argparse
import hashlib
import json
import logging
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd

from potato_blight.config import ExperimentCfg, load_config
from potato_blight.data.splits import assign_folds, check_no_leakage
from potato_blight.mlflow_utils import common_tags, log_json, setup
from potato_blight.train import train_split
from potato_blight.tune import search_space

log = logging.getLogger("potato_blight")


def inner_parts(development: pd.DataFrame, inner_fold: int) -> dict[str, pd.DataFrame]:
    parts = {"train": development[development["fold"] != inner_fold].copy(),
             "val": development[development["fold"] == inner_fold].copy()}
    check_no_leakage(parts)
    return parts


def run_nested(cfg: ExperimentCfg, df: pd.DataFrame, *, storage: str | None = None,
               folds: list[int] | None = None, output: str | Path = "configs/nested") -> dict:
    folds = list(range(cfg.data.n_splits)) if folds is None else folds
    if not folds or len(set(folds)) != len(folds) or any(k < 0 or k >= cfg.data.n_splits for k in folds):
        raise ValueError("La lista de folds externos es inválida")
    cv = df[df["dataset_id"].isin(cfg.data.train_datasets) & (df["fold"] >= 0)].copy()
    fingerprint = hashlib.sha256((cv.to_csv(index=False) + cfg.model_dump_json()).encode()).hexdigest()[:16]
    tags = common_tags("cv_parent", cfg.architecture, smoke_test=cfg.smoke_test,
                       dataset_ids=cfg.data.train_datasets)
    tags.update({"validation_protocol": "nested_grouped", "experiment_fingerprint": fingerprint})
    results = []
    with mlflow.start_run(run_name=f"nested-{cfg.architecture}", tags=tags) as parent:
        for outer_fold in folds:
            held_out = cv[cv["fold"] == outer_fold].copy()
            development = assign_folds(cv[cv["fold"] != outer_fold].copy(), cfg.data.train_datasets,
                                       cfg.tuning.inner_splits, cfg.train.seed + outer_fold)
            check_no_leakage({"development": development, "outer_test": held_out})
            study = optuna.create_study(
                study_name=f"{cfg.experiment}-{cfg.architecture}-outer{outer_fold}-{fingerprint}",
                storage=storage, load_if_exists=True, direction="maximize",
                sampler=optuna.samplers.TPESampler(seed=cfg.tuning.seed + outer_fold),
                # Reporta una media por fold interno, sin mezclar pasos de épocas entre folds.
                pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1),
            )

            def objective(trial: optuna.Trial, development=development, outer_fold=outer_fold) -> float:
                train_values, hp = search_space(trial, cfg.architecture, cfg.train.batch_size)
                candidate = cfg.model_copy(deep=True)
                candidate.train = candidate.train.model_copy(update=train_values)
                candidate.hparams = {**candidate.hparams, **hp}
                scores, best_epochs = [], []
                for inner_fold in range(cfg.tuning.inner_splits):
                    name = f"o{outer_fold}-t{trial.number}-i{inner_fold}"
                    result = train_split(candidate, inner_parts(development, inner_fold),
                                         run_type="nested_inner", run_name=name,
                                         fold=inner_fold, max_epochs=cfg.tuning.max_epochs,
                                         log_model=False, evaluate_test=False, nested=True)
                    scores.append(result.metrics["val_macro_f1"])
                    best_epochs.append(result.best_epoch)
                    trial.report(float(np.mean(scores)), inner_fold)
                    if trial.should_prune():
                        raise optuna.TrialPruned()
                trial.set_user_attr("best_epochs", best_epochs)
                return float(np.mean(scores))

            remaining = max(0, cfg.tuning.n_trials - len(study.trials))
            if remaining:
                study.optimize(objective, n_trials=remaining, timeout=cfg.tuning.timeout_hours * 3600,
                               gc_after_trial=True)
            selected = cfg.model_copy(deep=True)
            train_keys = {"lr", "weight_decay", "label_smoothing", "batch_size"}
            selected.train = selected.train.model_copy(update={k: v for k, v in study.best_params.items()
                                                               if k in train_keys})
            selected.hparams = {**selected.hparams, **{k: v for k, v in study.best_params.items()
                                                      if k not in train_keys}}
            # Reserva un grupo interno para early stopping/calibración; el test externo nunca participa.
            parts = {**inner_parts(development, 0), "test": held_out}
            result = train_split(selected, parts, run_type="cv_fold",
                                 run_name=f"{cfg.architecture}-outer{outer_fold}", fold=outer_fold, nested=True)
            mlflow.MlflowClient().set_tag(result.run_id, "validation_protocol", "nested_grouped")
            detail = {"outer_fold": outer_fold, "inner_best_macro_f1": study.best_value,
                      "best_params": study.best_params, "run_id": result.run_id,
                      "test_macro_f1": result.metrics["test_macro_f1"],
                      "config": selected.model_dump(), "study_name": study.study_name}
            destination = Path(output) / cfg.architecture / f"fold{outer_fold}-{fingerprint}.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(detail)
        scores = [result["test_macro_f1"] for result in results]
        summary = {"cv_mean_test_macro_f1": float(np.mean(scores)),
                   "cv_std_test_macro_f1": float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0}
        mlflow.log_metrics(summary)
        log_json({"folds": folds, "runs": [r["run_id"] for r in results],
                  "protocol": "nested_grouped", "inner_splits": cfg.tuning.inner_splits}, "cv_runs.json")
        return {"parent_run_id": parent.info.run_id, "summary": summary, "folds": results}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--storage", default="sqlite:///optuna-nested.db")
    parser.add_argument("--folds", type=int, nargs="+")
    args = parser.parse_args()
    cfg = load_config(args.config)
    setup(cfg.experiment)
    result = run_nested(cfg, pd.read_csv(cfg.data.manifest), storage=args.storage, folds=args.folds)
    log.info("Validación anidada terminada: %s", result["parent_run_id"])


if __name__ == "__main__":
    main()
