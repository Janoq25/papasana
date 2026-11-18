"""EDA reproducible con tablas CSV y figuras de 600 DPI a partir del manifest real."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from potato_blight import CLASSES


def generate(manifest: Path, output: Path) -> dict:
    df = pd.read_csv(manifest)
    report = json.loads(manifest.with_suffix(".informe.json").read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    by_class = pd.crosstab(df["dataset_id"], df["label"]).reindex(columns=CLASSES, fill_value=0)
    by_class.to_csv(output / "clases_por_fuente.csv")
    pd.crosstab(df.loc[df["fold"] >= 0, "fold"], df["label"]).to_csv(output / "clases_por_fold.csv")
    df[["width", "height"]].describe().to_csv(output / "resolucion.csv")
    summary = {**report, "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "imagenes_manifest": len(df), "entrenamiento": int((df["fold"] >= 0).sum()),
               "fuentes": {ds: {c: int(value) for c, value in values.items()}
                            for ds, values in by_class.to_dict(orient="index").items()},
               "nota": "Datos reales descargados. Las particiones respetan IDs de hoja y grupos de duplicados."}
    (output / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    short = ["Sano", "Síntomas compatibles\ncon tizón tardío", "Otra enfermedad\nfoliar"]
    fig, axes = plt.subplots(1, len(by_class), figsize=(11, 4), squeeze=False)
    for ax, (dataset_id, values) in zip(axes[0], by_class.iterrows(), strict=True):
        ax.bar(short, values.to_numpy(), color=["#237857", "#ae4b35", "#6b6296"])
        for index, value in enumerate(values):
            ax.text(index, value, str(int(value)), ha="center", va="bottom")
        ax.set_title(dataset_id)
        ax.set_ylabel("Imágenes tras control de calidad")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Distribución real de clases por fuente")
    fig.tight_layout()
    fig.savefig(output / "distribucion_clases.png", dpi=600)
    plt.close(fig)

    steps = [
        ("Fuentes públicas verificadas", f"{report['imagenes_originales']} imágenes originales"),
        ("Índice y deduplicación", f"{report['duplicados_exactos_eliminados']} copias exactas retiradas"),
        ("Control de etiquetas", f"{report['imagenes_con_etiquetas_en_conflicto']} imágenes en grupos conflictivos"),
        ("Grupos y particiones", f"{summary['entrenamiento']} imágenes de desarrollo · 5 folds"),
        ("Evaluación externa reservada", f"{report['externo_utilizable']} imágenes de PlantDoc"),
    ]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis("off")
    for index, (title, detail) in enumerate(steps):
        y = 0.87 - index * 0.18
        ax.text(0.5, y, title + "\n" + detail, ha="center", va="center", fontsize=12,
                bbox={"boxstyle": "round,pad=0.7", "facecolor": "#edf3f7", "edgecolor": "#6b879b"})
        if index < len(steps) - 1:
            ax.annotate("", xy=(0.5, y - 0.115), xytext=(0.5, y - 0.055),
                        arrowprops={"arrowstyle": "->", "color": "#415c72"})
    fig.suptitle("Preparación y EDA de PapaSana", fontsize=16)
    fig.text(0.5, 0.01, "Flujo de datos ejecutado. El entrenamiento y sus métricas se registran por separado.",
             ha="center", fontsize=10)
    fig.savefig(output / "flujo_preparacion_eda.png", dpi=600, bbox_inches="tight")
    plt.close(fig)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/eda"))
    args = parser.parse_args()
    print(json.dumps(generate(args.manifest, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
