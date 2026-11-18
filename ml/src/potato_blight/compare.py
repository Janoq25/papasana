"""Comparación estadística de los modelos a partir de los runs de validación cruzada registrados en MLflow.

- Friedman y Wilcoxon (Holm) sobre las métricas por bloque: cada (partición, escenario) es un bloque, donde el
  escenario es la prueba interna de la partición o cada dataset de validación externa.
- McNemar, DeLong y bootstrap sobre las predicciones fuera de partición (OOF): cada imagen de validación cruzada
  se predice una sola vez por modelo, así que todos los modelos se comparan sobre las mismas imágenes.
- El resultado se registra como `comparison.json` en un run `comparison`, que lee el Laboratorio de modelos.

Uso:  python -m potato_blight.compare [--metric macro_f1] [--incluir-smoke]
"""

import argparse
import logging
import tempfile
from itertools import combinations

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from sklearn.metrics import f1_score, matthews_corrcoef

from potato_blight import CLASSES
from potato_blight.mlflow_utils import common_tags, log_json, setup
from potato_blight.stats.tests import bootstrap_ci, delong, friedman, mcnemar, wilcoxon_holm

log = logging.getLogger("potato_blight")
PROB_COLS = [f"p_{c}" for c in CLASSES]


def _fold_runs(experiment: str, include_smoke: bool) -> pd.DataFrame:
    exp = mlflow.get_experiment_by_name(experiment)
    if exp is None:
        return pd.DataFrame()
    flt = "tags.run_type = 'cv_fold'" + ("" if include_smoke else " and tags.smoke_test = 'false'")
    return mlflow.search_runs([exp.experiment_id], filter_string=flt, output_format="pandas")


def _blocks(runs: pd.DataFrame, metric: str) -> dict[str, dict[str, float]]:
    """{modelo: {bloque: valor}} con bloques 'foldK:test' y 'foldK:external_<ds>'."""
    out: dict[str, dict[str, float]] = {}
    for _, r in runs.iterrows():
        arch, fold = r["tags.architecture"], r["tags.fold"]
        for col in r.index:
            if not col.startswith("metrics.") or not col.endswith(f"_{metric}"):
                continue
            scenario = col[len("metrics."):-len(metric) - 1]
            if scenario == "test" or scenario.startswith("external_"):
                if pd.notna(r[col]):
                    out.setdefault(arch, {})[f"fold{fold}:{scenario}"] = float(r[col])
    return out


def _oof_predictions(runs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    client, out = MlflowClient(), {}
    for arch, group in runs.groupby("tags.architecture"):
        frames = []
        for run_id in group["run_id"]:
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    p = client.download_artifacts(run_id, "predictions.csv", tmp)
                except Exception:  # noqa: BLE001 - run sin predicciones
                    continue
                df = pd.read_csv(p)
            frames.append(df[df["split"] == "test"])
        if frames:
            out[arch] = pd.concat(frames).drop_duplicates("path").set_index(["dataset_id", "path"]).sort_index()
    return out


def compare(experiment: str, metric: str = "macro_f1", include_smoke: bool = False) -> dict:
    runs = _fold_runs(experiment, include_smoke)
    if runs.empty:
        return {"estado": "sin_experimentos", "mensaje": "No hay runs de validación cruzada registrados."}
    blocks = _blocks(runs, metric)
    common = sorted(set.intersection(*[set(v) for v in blocks.values()])) if blocks else []
    scores = {m: [v[b] for b in common] for m, v in blocks.items()} if common else {}
    result: dict = {"estado": "ok", "metrica": metric, "bloques": common, "modelos": sorted(blocks),
                    "smoke_test": include_smoke,
                    "por_modelo": {m: {"media": float(np.mean(s)), "desviacion": float(np.std(s, ddof=1))
                                       if len(s) > 1 else 0.0, "n_bloques": len(s)} for m, s in scores.items()},
                    "friedman": friedman(scores) if scores else {"aplicable": False, "motivo": "Sin bloques comunes"},
                    "wilcoxon_holm": wilcoxon_holm(scores) if len(scores) >= 2 else []}

    oof = _oof_predictions(runs)
    if len(oof) >= 1:
        idx = sorted(set.intersection(*[set(df.index) for df in oof.values()]))
        aligned = {m: df.loc[idx] for m, df in oof.items()}
        result["oof_imagenes"] = len(idx)
        result["bootstrap"] = {}
        for m, df in aligned.items():
            y, probs = df["y_true"].to_numpy(), df[PROB_COLS].to_numpy()
            result["bootstrap"][m] = {
                "macro_f1": bootstrap_ci(lambda yt, p: f1_score(yt, p.argmax(1), average="macro"), y, probs),
                "mcc": bootstrap_ci(lambda yt, p: matthews_corrcoef(yt, p.argmax(1)), y, probs),
            }
        result["mcnemar"], result["delong"] = [], []
        late = CLASSES.index("sintomas_compatibles_tizon_tardio")
        for a, b in combinations(sorted(aligned), 2):
            da, db = aligned[a], aligned[b]
            y = da["y_true"].to_numpy()
            pa, pb = da[PROB_COLS].to_numpy(), db[PROB_COLS].to_numpy()
            result["mcnemar"].append({"modelo_a": a, "modelo_b": b, **mcnemar(y, pa.argmax(1), pb.argmax(1))})
            result["delong"].append({"modelo_a": a, "modelo_b": b, "clase": CLASSES[late],
                                     **delong(y == late, pa[:, late], pb[:, late])})
    return result


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experiment", default="papasana-ap01")
    ap.add_argument("--metric", default="macro_f1", choices=["macro_f1", "mcc", "accuracy", "macro_auc_roc"])
    ap.add_argument("--incluir-smoke", action="store_true", help="Incluir runs de prueba de humo (solo pruebas)")
    args = ap.parse_args(argv)
    setup(args.experiment)
    result = compare(args.experiment, args.metric, args.incluir_smoke)
    tags = common_tags("comparison", "todas", smoke_test=args.incluir_smoke, dataset_ids=[])
    with mlflow.start_run(run_name=f"comparacion-{args.metric}", tags=tags):
        log_json(result, "comparison.json")
    log.info("Comparación registrada: %s modelos, estado %s", len(result.get("modelos", [])), result["estado"])


if __name__ == "__main__":
    main()

