"""Entrenamiento con registro en MLflow.

Modos:
  cv     validaciÃ³n cruzada agrupada: un run padre (`cv_parent`) con un run anidado por particiÃ³n (`cv_fold`).
         Cada particiÃ³n calibra la temperatura en su validaciÃ³n interna y evalÃºa su prueba y la prueba externa.
  final  modelo para producciÃ³n: entrena con todas las particiones salvo la de validaciÃ³n (early stopping y
         calibraciÃ³n) y evalÃºa la prueba externa. Es el run que se registra en el Model Registry.

Uso:  python -m potato_blight.train --config configs/resnet50.yaml --mode cv
      python -m potato_blight.train --config configs/resnet50.yaml --mode final
"""

import argparse
import copy
import logging
import math
import random
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

from potato_blight import CLASSES
from potato_blight.calibration import fit_temperature, nll, reliability, softmax
from potato_blight.config import ExperimentCfg, load_config
from potato_blight.data.dataset import ManifestDataset, eval_transform, train_transform
from potato_blight.data.splits import check_no_leakage, external_split, fold_split
from potato_blight.metrics import compute_metrics, scalar_metrics
from potato_blight.mlflow_utils import common_tags, log_json, setup
from potato_blight.models.architectures import SPECS, build_model
from potato_blight.models.serialize import make_config, save_model_dir

log = logging.getLogger("potato_blight")


@dataclass
class FoldResult:
    run_id: str
    metrics: dict[str, float]
    best_epoch: int
    stopped_early: bool
    evaluation: dict = field(default_factory=dict)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _loader(df, cfg: ExperimentCfg, transform, shuffle: bool) -> DataLoader:
    ds = ManifestDataset(df, cfg.data.roots, transform)
    return DataLoader(ds, batch_size=cfg.train.batch_size, shuffle=shuffle, num_workers=cfg.train.num_workers,
                      pin_memory=torch.cuda.is_available(), drop_last=False)


def classifier_parameters(model: nn.Module) -> list[nn.Parameter]:
    classifier = model.get_classifier() if hasattr(model, "get_classifier") else model.head
    return list(classifier.parameters())


@torch.no_grad()
def predict_logits(model: nn.Module, loader: DataLoader, dev: torch.device, *,
                   amp: bool = True, amp_dtype: str = "float16") -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    logits, labels = [], []
    for x, y, _ in loader:
        with torch.autocast(dev.type, enabled=amp and dev.type == "cuda", dtype=getattr(torch, amp_dtype)):
            out = model(x.to(dev, non_blocking=True))
        chunk = out.float().cpu().numpy()
        if not np.isfinite(chunk).all():
            raise FloatingPointError(f"Logits no finitos con precisión {amp_dtype}; no se calculan métricas.")
        logits.append(chunk)
        labels.append(y.numpy())
    if not logits:
        return np.zeros((0, len(CLASSES))), np.zeros(0, dtype=int)
    return np.concatenate(logits), np.concatenate(labels)


def _evaluate_split(name: str, logits, labels, temperature: float) -> dict:
    probs = softmax(logits, temperature)
    out = compute_metrics(labels, probs, CLASSES)
    raw = softmax(logits, 1.0)
    out["calibration"] = {"temperature": temperature, "nll_before": nll(raw, labels), "nll_after": nll(probs, labels),
                          "before": reliability(raw, labels), "after": reliability(probs, labels)}
    out["split"] = name
    return out


def _predictions_frame(df: pd.DataFrame, logits, labels, temperature: float, split: str) -> pd.DataFrame:
    probs = softmax(logits, temperature)
    out = pd.DataFrame({"split": split, "path": df["path"].values, "dataset_id": df["dataset_id"].values,
                        "group_id": df["group_id"].values, "y_true": labels})
    for i, c in enumerate(CLASSES):
        out[f"p_{c}"] = probs[:, i]
    return out


def train_split(cfg: ExperimentCfg, parts: dict[str, pd.DataFrame], *, run_type: str, run_name: str,
                fold: int | None = None, trial=None, max_epochs: int | None = None, log_model: bool = True,
                evaluate_test: bool = True, nested: bool = False) -> FoldResult:
    """Entrena con parts['train'], selecciona y calibra con parts['val'] y evalÃºa 'test'/'external_*'."""
    seed_everything(cfg.train.seed + (fold or 0))
    check_no_leakage(parts)
    dev = device()
    if cfg.train.require_cuda and dev.type != "cuda":
        raise RuntimeError("Este perfil exige GPU CUDA. No se cambia silenciosamente a CPU.")
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    torch.set_num_threads(min(4, torch.get_num_threads()))
    img_size = cfg.img_size or SPECS[cfg.architecture].default_img_size
    train_loader = _loader(parts["train"], cfg, train_transform(img_size), shuffle=True)
    eval_tf = eval_transform(img_size)
    loaders = {k: _loader(v, cfg, eval_tf, shuffle=False) for k, v in parts.items() if k != "train" and len(v)}
    if "val" not in loaders:
        raise ValueError("La validaciÃ³n interna estÃ¡ vacÃ­a.")

    model = build_model(cfg.architecture, len(CLASSES), img_size=img_size, pretrained=cfg.pretrained,
                        **copy.deepcopy(cfg.hparams)).to(dev)
    log.info("Entrenamiento en %s | modelo=%s | GPU=%s", dev, next(model.parameters()).device,
             torch.cuda.get_device_name() if dev.type == "cuda" else "sin GPU")
    head = classifier_parameters(model)
    head_ids = {id(p) for p in head}
    backbone = [p for p in model.parameters() if id(p) not in head_ids]
    opt = torch.optim.AdamW([{"params": backbone, "lr": cfg.train.lr * cfg.train.backbone_lr_factor},
                             {"params": head, "lr": cfg.train.lr}], weight_decay=cfg.train.weight_decay)
    epochs = max_epochs or cfg.train.epochs
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    # Pesos por clase inversos a la frecuencia del entrenamiento (las clases suelen estar desbalanceadas)
    counts = parts["train"]["label"].value_counts().reindex(CLASSES).fillna(0).to_numpy(dtype=float)
    weights = torch.tensor(np.where(counts > 0, counts.sum() / (len(CLASSES) * np.maximum(counts, 1)), 0.0),
                           dtype=torch.float32, device=dev)
    loss_fn = nn.CrossEntropyLoss(weight=weights, label_smoothing=cfg.train.label_smoothing)
    amp_enabled = cfg.train.amp and dev.type == "cuda"
    amp_dtype = getattr(torch, cfg.train.amp_dtype)
    if amp_enabled and amp_dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
        raise RuntimeError("La GPU no admite bfloat16; elija float16 o desactive AMP.")
    scaler = torch.amp.GradScaler(enabled=amp_enabled and amp_dtype == torch.float16)

    datasets = sorted(set().union(*[set(p["dataset_id"]) for p in parts.values()]))
    tags = common_tags(run_type, cfg.architecture, smoke_test=cfg.smoke_test, dataset_ids=datasets)
    if fold is not None:
        tags["fold"] = str(fold)
    t0 = time.time()
    with mlflow.start_run(run_name=run_name, nested=nested, tags=tags) as run:
        mlflow.log_params({"architecture": cfg.architecture, "img_size": img_size, "pretrained": cfg.pretrained,
                           **{f"hp_{k}": v for k, v in cfg.hparams.items()},
                           **{f"train_{k}": v for k, v in cfg.train.model_dump().items()},
                           "epochs_budget": epochs, "device": dev.type,
                           **{f"n_{k}": len(v) for k, v in parts.items()}})
        best_f1, best_loss, best_state, best_epoch, bad, stopped = -1.0, math.inf, None, 0, 0, False
        for epoch in range(1, epochs + 1):
            frozen = epoch <= cfg.train.freeze_epochs
            for parameter in backbone:
                parameter.requires_grad_(not frozen)
            model.train()
            if frozen:
                for module in model.modules():
                    if isinstance(module, nn.modules.batchnorm._BatchNorm):
                        module.eval()
            total, seen = 0.0, 0
            opt.zero_grad(set_to_none=True)
            for batch_index, (x, y, _) in enumerate(train_loader):
                x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
                with torch.autocast(dev.type, enabled=amp_enabled, dtype=amp_dtype):
                    loss = loss_fn(model(x), y)
                if not torch.isfinite(loss):
                    raise FloatingPointError(f"Pérdida no finita en época {epoch}, lote {batch_index}.")
                window_start = (batch_index // cfg.train.accumulation_steps) * cfg.train.accumulation_steps
                window_size = min(cfg.train.accumulation_steps, len(train_loader) - window_start)
                scaler.scale(loss / window_size).backward()
                if (batch_index + 1) % cfg.train.accumulation_steps == 0 or batch_index + 1 == len(train_loader):
                    scaler.unscale_(opt)
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    scaler.step(opt)
                    scaler.update()
                    opt.zero_grad(set_to_none=True)
                total += float(loss.detach()) * len(y)
                seen += len(y)
            sched.step()
            v_logits, v_labels = predict_logits(model, loaders["val"], dev, amp=cfg.train.amp,
                                            amp_dtype=cfg.train.amp_dtype)
            v_loss = float(nn.functional.cross_entropy(torch.from_numpy(v_logits), torch.from_numpy(v_labels)))
            v_f1 = compute_metrics(v_labels, softmax(v_logits), CLASSES, curves=False)["macro_f1"] or 0.0
            mlflow.log_metrics({"train_loss": total / max(seen, 1), "val_loss": v_loss, "val_macro_f1_epoch": v_f1,
                                "lr": sched.get_last_lr()[0]}, step=epoch)
            log.info("%s época %s/%s: loss=%.4f val_F1=%.4f tiempo=%.1fs backbone=%s", run_name, epoch,
                     epochs, total / max(seen, 1), v_f1, time.time() - t0, "congelado" if frozen else "ajustable")
            if v_f1 > best_f1 or (v_f1 == best_f1 and v_loss < best_loss):
                best_f1, best_loss, best_epoch, bad = v_f1, v_loss, epoch, 0
                best_state = copy.deepcopy(model.state_dict())
            else:
                bad += 1
            if trial is not None:
                trial.report(v_f1, epoch)
                if trial.should_prune():
                    mlflow.set_tag("optuna_pruned", "true")
                    import optuna

                    raise optuna.TrialPruned()
            if bad >= cfg.train.patience:
                stopped = True
                break
            if cfg.train.max_minutes and (time.time() - t0) / 60 > cfg.train.max_minutes:
                stopped = True
                mlflow.set_tag("stopped_by_time_budget", "true")
                break

        for parameter in backbone:
            parameter.requires_grad_(True)
        model.load_state_dict(best_state)
        v_logits, v_labels = predict_logits(model, loaders["val"], dev, amp=cfg.train.amp,
                                            amp_dtype=cfg.train.amp_dtype)
        temperature = fit_temperature(v_logits, v_labels)
        evaluation = {"val": _evaluate_split("val", v_logits, v_labels, temperature)}
        metrics = {"temperature": temperature, "best_epoch": best_epoch, **scalar_metrics(evaluation["val"], "val")}
        predictions = []
        for name, loader in loaders.items():
            if name == "val" or (name == "test" and not evaluate_test):
                continue
            logits, labels = predict_logits(model, loader, dev, amp=cfg.train.amp,
                                              amp_dtype=cfg.train.amp_dtype)
            evaluation[name] = _evaluate_split(name, logits, labels, temperature)
            metrics.update(scalar_metrics(evaluation[name], name))
            metrics[f"{name}_ece"] = evaluation[name]["calibration"]["after"]["ece"]
            metrics[f"{name}_ece_before"] = evaluation[name]["calibration"]["before"]["ece"]
            predictions.append(_predictions_frame(parts[name], logits, labels, temperature, name))
        elapsed = time.time() - t0
        metrics["train_seconds"] = elapsed
        metrics["gpu_hours"] = elapsed / 3600 if dev.type == "cuda" else 0.0
        if dev.type == "cuda":
            metrics["gpu_peak_memory_mb"] = torch.cuda.max_memory_allocated() / 1024**2
            mlflow.set_tag("gpu_name", torch.cuda.get_device_name())
        mlflow.log_metrics(metrics)
        mlflow.set_tag("stopped_early", str(stopped).lower())
        log_json(evaluation, "evaluation.json")
        if predictions:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "predictions.csv"
                pd.concat(predictions).to_csv(p, index=False)
                mlflow.log_artifact(str(p))
        if log_model:
            mcfg = make_config(cfg.architecture, CLASSES, img_size=img_size, hparams=cfg.hparams,
                               temperature=temperature, smoke_test=cfg.smoke_test,
                               extra={"run_id": run.info.run_id, "train_datasets": cfg.data.train_datasets,
                                      "inference_amp": cfg.train.amp, "inference_amp_dtype": cfg.train.amp_dtype})
            with tempfile.TemporaryDirectory() as tmp:
                save_model_dir(model.cpu(), mcfg, Path(tmp) / "model")
                mlflow.log_artifacts(str(Path(tmp) / "model"), artifact_path="model")
        del model, opt, scaler
        if dev.type == "cuda":
            torch.cuda.empty_cache()
        return FoldResult(run.info.run_id, metrics, best_epoch, stopped, evaluation)


def _external_parts(cfg: ExperimentCfg, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ext = external_split(df, cfg.data.external_datasets, cfg.data.train_datasets)
    return {f"external_{ds}": ext[ext["dataset_id"] == ds] for ds in cfg.data.external_datasets
            if (ext["dataset_id"] == ds).any()}


def run_cv(cfg: ExperimentCfg, df: pd.DataFrame, folds: list[int] | None = None) -> dict:
    folds = folds if folds is not None else list(range(cfg.data.n_splits))
    externals = _external_parts(cfg, df)
    tags = common_tags("cv_parent", cfg.architecture, smoke_test=cfg.smoke_test,
                       dataset_ids=sorted(set(df["dataset_id"])))
    with mlflow.start_run(run_name=f"cv-{cfg.architecture}", tags=tags) as parent:
        results = []
        for k in folds:
            parts = {**fold_split(df, k, cfg.data.n_splits), **externals}
            results.append(train_split(cfg, parts, run_type="cv_fold", run_name=f"{cfg.architecture}-fold{k}",
                                       fold=k, nested=True))
        keys = set.intersection(*[set(r.metrics) for r in results])
        summary = {}
        for key in sorted(keys):
            vals = np.array([r.metrics[key] for r in results], dtype=float)
            summary[f"cv_mean_{key}"] = float(vals.mean())
            summary[f"cv_std_{key}"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
        mlflow.log_metrics(summary)
        log_json({"folds": folds, "runs": [r.run_id for r in results]}, "cv_runs.json")
        return {"parent_run_id": parent.info.run_id, "fold_runs": [r.run_id for r in results], "summary": summary}


def run_final(cfg: ExperimentCfg, df: pd.DataFrame, val_fold: int = 0, cv_parent_run_id: str | None = None):
    cv = df[df["fold"] >= 0]
    parts = {"train": cv[cv["fold"] != val_fold], "val": cv[cv["fold"] == val_fold], **_external_parts(cfg, df)}
    result = train_split(cfg, parts, run_type="final", run_name=f"final-{cfg.architecture}")
    if cv_parent_run_id:
        mlflow.MlflowClient().set_tag(result.run_id, "cv_parent_run_id", cv_parent_run_id)
    return result


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--mode", choices=["cv", "final"], default="cv")
    ap.add_argument("--folds", type=int, nargs="*", default=None)
    ap.add_argument("--cv-parent-run-id", default=None, help="Run padre de la validaciÃ³n cruzada (modo final)")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    setup(cfg.experiment)
    df = pd.read_csv(cfg.data.manifest)
    if args.mode == "cv":
        out = run_cv(cfg, df, args.folds)
        log.info("ValidaciÃ³n cruzada registrada: %s", out["parent_run_id"])
    else:
        res = run_final(cfg, df, cv_parent_run_id=args.cv_parent_run_id)
        log.info("Modelo final registrado en el run %s (regÃ­strelo con potato_blight.register)", res.run_id)


if __name__ == "__main__":
    main()
