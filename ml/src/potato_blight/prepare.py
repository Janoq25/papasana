"""Prepara el manifest: índice de cada dataset → deduplicación (también entre datasets) → particiones agrupadas.

Uso:  python -m potato_blight.prepare --config configs/base.yaml
Escribe el manifest (CSV) indicado en `data.manifest` y un informe `<manifest>.informe.json`.
"""

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from potato_blight.config import ExperimentCfg, load_config
from potato_blight.data.dedup import assign_groups, dedup_report
from potato_blight.data.index import build_manifest
from potato_blight.data.registry import Registry, load_registry
from potato_blight.data.splits import assign_folds, external_split

log = logging.getLogger("potato_blight")


def prepare(cfg: ExperimentCfg, registry: Registry, *, allow_unverified: bool = False) -> tuple[pd.DataFrame, dict]:
    frames = []
    for ds_id, root in cfg.data.roots.items():
        entry = registry.get(ds_id)
        frames.append(build_manifest(entry, root, allow_unverified=allow_unverified))
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    grouped = assign_groups(raw, cfg.data.near_duplicate_distance)
    # Los grupos visuales con etiquetas incompatibles necesitan revisión.
    clean = grouped[~grouped["label_conflict"]].copy()
    df = assign_folds(clean, cfg.data.train_datasets, cfg.data.n_splits, cfg.train.seed)
    ext = external_split(df, cfg.data.external_datasets, cfg.data.train_datasets)
    report = dedup_report(raw, grouped)
    report["cuarentena"] = grouped.loc[grouped["label_conflict"],
                                        ["dataset_id", "path", "label", "group_id"]].to_dict(orient="records")
    report["grupos_aceptados"] = int(df["group_id"].nunique())
    folds = df[df["fold"] >= 0]["fold"].value_counts().sort_index()
    report["por_particion"] = {str(k): int(v) for k, v in folds.items()}
    report["externo_utilizable"] = int(len(ext))
    report["externo_excluido_por_compartido"] = int(df["dataset_id"].isin(cfg.data.external_datasets).sum() - len(ext))
    report["por_clase"] = {k: int(v) for k, v in df["label"].value_counts().items()}
    return df, report


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True)
    ap.add_argument("--registry", default=None, help="Ruta de datasets.yaml (por defecto ml/datasets.yaml)")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    df, report = prepare(cfg, load_registry(args.registry))
    out = Path(cfg.data.manifest)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    out.with_suffix(".informe.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Manifest: %s (%s imágenes). Informe: %s", out, len(df), json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
