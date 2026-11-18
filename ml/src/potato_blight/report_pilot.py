"""Exporta curvas y matrices del piloto real registrado en MLflow."""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd


def export(root: Path) -> None:
    summary = json.loads((root / "resultados.json").read_text(encoding="utf-8"))
    client = mlflow.MlflowClient()
    profiles, histories = [], []
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for name, item in summary["profiles"].items():
        values = item["metrics"]
        profiles.append({"perfil": name, "F1_validacion": values["val_macro_f1"],
                         "segundos": values["train_seconds"],
                         "pico_VRAM_MB": values.get("gpu_peak_memory_mb"), "run_id": item["run_id"]})
        for key, axis in (("val_macro_f1_epoch", axes[0]), ("train_loss", axes[1])):
            history = client.get_metric_history(item["run_id"], key)
            axis.plot([m.step for m in history], [m.value for m in history], marker="o", label=name)
            histories.extend({"perfil": name, "metrica": key, "epoca": m.step, "valor": m.value} for m in history)
    for ax in axes:
        ax.set_xlabel("Época")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend()
    axes[0].set_ylabel("F1 macro de validación interna")
    axes[0].set_ylim(0, 1.02)
    axes[1].set_ylabel("Pérdida de entrenamiento")
    fig.suptitle("Piloto real de ResNet50 en RTX 3050")
    fig.tight_layout()
    fig.savefig(root / "curvas_entrenamiento.png", dpi=600)
    plt.close(fig)
    pd.DataFrame(profiles).to_csv(root / "comparacion_perfiles.csv", index=False)
    pd.DataFrame(histories).to_csv(root / "historial_epocas.csv", index=False)
    path = mlflow.artifacts.download_artifacts(run_id=summary["final_run_id"], artifact_path="evaluation.json")
    evaluation = json.loads(Path(path).read_text(encoding="utf-8"))
    (root / "evaluacion_final.json").write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    names = [name for name in ("val", "external_plantdoc_papa") if name in evaluation]
    fig, axes = plt.subplots(1, len(names), figsize=(11, 5), squeeze=False)
    labels = ["Sano", "Compatible\ncon TT", "Otra enf.\nfoliar"]
    for ax, name in zip(axes[0], names, strict=True):
        matrix = np.array(evaluation[name]["confusion_matrix"])
        ax.imshow(matrix, cmap="Blues")
        for (i, j), value in np.ndenumerate(matrix):
            ax.text(j, i, str(value), ha="center", va="center",
                    color="white" if value > matrix.max() / 2 else "black")
        ax.set_xticks(range(3), labels, fontsize=9)
        ax.set_yticks(range(3), labels, fontsize=9)
        ax.set_xlabel("Predicción")
        ax.set_ylabel("Etiqueta de la fuente")
        ax.set_title("Validación interna" if name == "val" else "PlantDoc externo · sin casos sanos")
    fig.suptitle("Matrices de confusión del candidato final")
    fig.text(0.5, 0.02, "TT: síntomas compatibles con tizón tardío", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.94))
    fig.savefig(root / "matrices_confusion.png", dpi=600)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/piloto-resnet50"))
    export(parser.parse_args().root)


if __name__ == "__main__":
    main()
