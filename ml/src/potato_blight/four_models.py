"""Entrena cuatro candidatos CUDA con el mismo holdout y compara calidad y tiempo.

Uso: python -m potato_blight.four_models
PlantDoc se consulta después de fijar la selección interna; sus resultados son descriptivos.
"""

import argparse
import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from potato_blight import CLASSES
from potato_blight.config import ExperimentCfg, load_config
from potato_blight.data.dataset import ManifestDataset, eval_transform
from potato_blight.data.splits import check_no_leakage, external_split
from potato_blight.explain.gradcam import GradCAM
from potato_blight.metrics import scalar_metrics
from potato_blight.mlflow_utils import log_json, setup
from potato_blight.models.architectures import QUICK_COMPARISON_ARCHITECTURES, SPECS, build_model
from potato_blight.models.serialize import load_model_dir
from potato_blight.train import _evaluate_split, _predictions_frame, predict_logits, train_split

log = logging.getLogger("potato_blight")
VAL_FOLD = 1


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def development_parts(df: pd.DataFrame, cfg: ExperimentCfg) -> dict[str, pd.DataFrame]:
    dev = df[df["dataset_id"].isin(cfg.data.train_datasets) & (df["fold"] >= 0)]
    parts = {"train": dev[dev["fold"] != VAL_FOLD].copy(), "val": dev[dev["fold"] == VAL_FOLD].copy()}
    check_no_leakage(parts)
    if any(set(part["label"]) != set(CLASSES) for part in parts.values()):
        raise ValueError("El desarrollo debe contener las tres clases en entrenamiento y validación.")
    return parts


def choose_internal(rows: list[dict], previous_f1: float) -> dict:
    reference = next(row for row in rows if row["architecture"] == "resnet50")
    threshold = max(previous_f1, reference["metrics"]["val_macro_f1"])
    eligible = [row for row in rows if row["metrics"]["val_macro_f1"] >= threshold]
    fastest = min(eligible, key=lambda row: row["metrics"]["train_seconds"]) if eligible else None
    return {"criterion": "Menor tiempo entre candidatos cuyo F1 interno no es inferior a la referencia observada.",
            "minimum_observed_f1": threshold,
            "recommended_architecture": fastest["architecture"] if fastest else "resnet50",
            "recommended_source": "current_comparison" if fastest else "previous_resnet50",
            "best_internal_architecture": max(rows, key=lambda row: row["metrics"]["val_macro_f1"])["architecture"],
            "fastest_architecture": min(rows, key=lambda row: row["metrics"]["train_seconds"])["architecture"],
            "statistical_noninferiority_proven": False,
            "external_used_for_selection": False}


def gpu_probe(arch: str, batch_size: int, amp_dtype: str = "float16") -> dict:
    torch.manual_seed(2026)
    torch.cuda.reset_peak_memory_stats()
    model = build_model(arch, 3, img_size=224, pretrained=False).cuda().train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4)
    dtype = getattr(torch, amp_dtype)
    scaler = torch.amp.GradScaler(enabled=dtype == torch.float16)
    x = torch.randn(batch_size, 3, 224, 224, device="cuda")
    y = torch.arange(batch_size, device="cuda") % 3

    def step(model=model, optimizer=optimizer, scaler=scaler, x=x, y=y, dtype=dtype):
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast("cuda", dtype=dtype):
            loss = torch.nn.functional.cross_entropy(model(x), y)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

    for _ in range(3):
        step()
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(8):
        step()
    torch.cuda.synchronize()
    result = {"architecture": arch, "batch_size": batch_size, "device": str(x.device), "amp_dtype": amp_dtype,
              "parameters_three_classes": sum(p.numel() for p in model.parameters()),
              "synthetic_step_ms": 1000 * (time.perf_counter() - start) / 8,
              "peak_allocated_mb": torch.cuda.max_memory_allocated() / 1024**2,
              "note": "Solo tiempo y memoria de entrenamiento sintético; no mide calidad."}
    del step, model, optimizer, scaler, x, y
    torch.cuda.empty_cache()
    return result


def evaluate_external(row: dict, cfg: ExperimentCfg, df: pd.DataFrame, destination: Path) -> dict:
    external = external_split(df, cfg.data.external_datasets, cfg.data.train_datasets)
    check_no_leakage({**development_parts(df, cfg), "external": external})
    model, model_cfg = load_model_dir(destination / "model")
    model = model.cuda().eval()
    evaluation = row["evaluation"].copy()
    metric_values = {}
    for ds_id, group in external.groupby("dataset_id"):
        loader = DataLoader(ManifestDataset(group, cfg.data.roots, eval_transform(cfg.img_size)),
                            batch_size=cfg.train.batch_size, num_workers=0, pin_memory=True)
        logits, labels = predict_logits(model, loader, torch.device("cuda"), amp=cfg.train.amp,
                                        amp_dtype=cfg.train.amp_dtype)
        name = f"external_{ds_id}"
        item = _evaluate_split(name, logits, labels, model_cfg["temperature"])
        evaluation[name] = item
        metric_values.update(scalar_metrics(item, name))
        metric_values[f"{name}_ece"] = item["calibration"]["after"]["ece"]
        predictions = _predictions_frame(group, logits, labels, model_cfg["temperature"], name)
        predictions.to_csv(destination / f"predictions_{ds_id}.csv", index=False)
    sample = development_parts(df, cfg)["val"].iloc[:1]
    x, _, _ = ManifestDataset(sample, cfg.data.roots, eval_transform(cfg.img_size))[0]
    explainer = GradCAM(model, cfg.architecture)
    probabilities, cam = explainer(x.unsqueeze(0).cuda(), temperature=model_cfg["temperature"])
    explainer.remove()
    if not np.isfinite(cam).all() or min(cam.shape) < 2 or not torch.isfinite(probabilities).all():
        raise RuntimeError("Falló la comprobación espacial de Grad-CAM del modelo recargado.")
    verification = {"model_device": str(next(model.parameters()).device), "gradcam_shape": list(cam.shape),
                    "checkpoint_sha256": hashlib.sha256((destination / "model/model.pt").read_bytes()).hexdigest(),
                    "reload_and_gradcam_passed": True}
    save_json(destination / "verification.json", verification)
    save_json(destination / "evaluation.json", evaluation)
    with mlflow.start_run(run_id=row["run_id"]):
        mlflow.log_metrics(metric_values)
        log_json(evaluation, "evaluation.json")
        log_json(verification, "reload_verification.json")
    row["metrics"].update(metric_values)
    row["evaluation"] = evaluation
    row["external_evaluated"] = True
    row["verification"] = verification
    del model, explainer, x
    torch.cuda.empty_cache()
    return row


def report(output: Path, summary: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    records = [{"modelo": row["architecture"], "F1_interno": row["metrics"]["val_macro_f1"],
                "F1_PlantDoc_dos_clases": row["metrics"].get("external_plantdoc_papa_macro_f1"),
                "exactitud_PlantDoc": row["metrics"].get("external_plantdoc_papa_accuracy"),
                "segundos_entrenamiento": row["metrics"]["train_seconds"],
                "pico_VRAM_MB": row["metrics"].get("gpu_peak_memory_mb"),
                "parametros": row["probe"]["parameters_three_classes"],
                "peso_archivo_MB": row["checkpoint_mb"], "run_id": row["run_id"]}
               for row in summary["models"]]
    pd.DataFrame(records).to_csv(output / "comparison.csv", index=False)
    labels = ["ResNet50", "EffNetV2\nB0", "MobileNetV4\nMedium", "EfficientViT\nB1"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    panels = [("F1_interno", "F1 interno · tres clases"),
              ("F1_PlantDoc_dos_clases", "PlantDoc · F1 en dos clases presentes"),
              ("segundos_entrenamiento", "Tiempo de entrenamiento en GPU (s)")]
    for ax, (key, title) in zip(axes, panels, strict=True):
        values = [record[key] or 0 for record in records]
        ax.bar(labels, values, color=["#44677c", "#187c6b", "#706298", "#b35c3d"])
        ax.set_title(title, fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", labelsize=9)
        ax.set_ylim(0, 1.1 if key != "segundos_entrenamiento" else max(values) * 1.18)
        for i, value in enumerate(values):
            ax.text(i, value, f"{value:.3f}" if key != "segundos_entrenamiento" else f"{value:.1f}",
                    ha="center", va="bottom", fontsize=9)
    fig.suptitle("Cuatro arquitecturas · mismo holdout y presupuesto máximo", fontsize=14)
    fig.text(0.5, 0.01, "Piloto descriptivo. PlantDoc no incluye hojas sanas y no intervino en la selección.",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(output / "comparison.png", dpi=600)
    plt.close(fig)
    client = mlflow.MlflowClient()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, row in zip(axes.flat, summary["models"], strict=True):
        history = client.get_metric_history(row["run_id"], "val_macro_f1_epoch")
        ax.plot([item.step for item in history], [item.value for item in history], marker="o", markersize=3)
        ax.set_title(SPECS[row["architecture"]].display_name)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("Época")
        ax.set_ylabel("F1 macro interno")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output / "learning_curves.png", dpi=600)
    plt.close(fig)


def run(output: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("Esta comparación requiere CUDA; no se ejecuta en CPU.")
    torch.set_num_threads(4)
    configs = [load_config(f"configs/quick4_{arch}.yaml") for arch in QUICK_COMPARISON_ARCHITECTURES]
    cfg0 = configs[0]
    df = pd.read_csv(cfg0.data.manifest)
    source_paths = list(Path(__file__).parent.rglob("*.py"))
    contract = {"configs": [cfg.model_dump() for cfg in configs], "validation_fold": VAL_FOLD,
                "manifest_sha256": hashlib.sha256(Path(cfg0.data.manifest).read_bytes()).hexdigest(),
                "source_sha256": {str(path.relative_to(Path(__file__).parent)):
                                  hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source_paths)}}
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    save_json(output / "contract.json", contract)
    setup(cfg0.experiment)
    previous = json.loads(Path("data/piloto-resnet50/resultados.json").read_text(encoding="utf-8"))
    rows = []
    for cfg in configs:
        destination = output / cfg.architecture
        saved = destination / "training.json"
        if saved.exists():
            row = json.loads(saved.read_text(encoding="utf-8"))
            if row["fingerprint"] != fingerprint:
                raise RuntimeError("Cambió el código, manifest o configuración. Use otro directorio de salida.")
            log.info("Reutilizando candidato completo: %s", cfg.architecture)
        else:
            log.info("Comprobando GPU y memoria: %s", cfg.architecture)
            probe = gpu_probe(cfg.architecture, cfg.train.batch_size, cfg.train.amp_dtype)
            log.info("%s: paso sintético %.1f ms, %.0f MB, %s", cfg.architecture,
                     probe["synthetic_step_ms"], probe["peak_allocated_mb"], probe["device"])
            result = train_split(cfg, development_parts(df, cfg), run_type="final",
                                 run_name=f"quick4-{cfg.architecture}")
            client = mlflow.MlflowClient()
            for key, value in {"validation_protocol": "four_model_grouped_holdout",
                               "comparison_fingerprint": fingerprint}.items():
                client.set_tag(result.run_id, key, value)
            folder = mlflow.artifacts.download_artifacts(run_id=result.run_id, artifact_path="model")
            shutil.copytree(folder, destination / "model", dirs_exist_ok=True)
            row = {"architecture": cfg.architecture, "run_id": result.run_id, "metrics": result.metrics,
                   "evaluation": result.evaluation, "fingerprint": fingerprint, "probe": probe,
                   "best_epoch": result.best_epoch, "external_evaluated": False,
                   "checkpoint_mb": (destination / "model/model.pt").stat().st_size / 1024**2}
            save_json(destination / "config.json", cfg.model_dump())
            save_json(saved, row)
        rows.append(row)
        save_json(output / "progress.json", {"finished_training": [item["architecture"] for item in rows]})
    selection = choose_internal(rows, previous["final_metrics"]["val_macro_f1"])
    save_json(output / "selection_before_external.json", selection)
    for row, cfg in zip(rows, configs, strict=True):
        if not row["external_evaluated"]:
            log.info("Evaluación externa descriptiva y recarga CUDA: %s", cfg.architecture)
            evaluate_external(row, cfg, df, output / cfg.architecture)
            save_json(output / cfg.architecture / "training.json", row)
    summary = {"gpu": torch.cuda.get_device_name(), "torch": torch.__version__, "fingerprint": fingerprint,
               "contract": contract, "selection": selection, "models": rows,
               "limits": ["Un holdout agrupado; no es la validación anidada completa.",
                          "La no inferioridad estadística no se ha demostrado.",
                          "PlantDoc fue observado en el piloto previo; es evaluación descriptiva y carece de sanos.",
                          "Sin promoción automática a la aplicación."]}
    save_json(output / "results.json", summary)
    report(output, summary)
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/comparacion-cuatro"))
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        report(args.output, json.loads((args.output / "results.json").read_text(encoding="utf-8")))
    else:
        result = run(args.output)
        print(json.dumps({"selection": result["selection"], "models": [row["architecture"]
                          for row in result["models"]]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
