"""Prueba de humo del pipeline completo con imágenes SINTÉTICAS (criterio de cierre de la Fase 4).

Genera el dataset sintético → manifest → deduplicación → particiones agrupadas → entrenamiento corto (sin pesos
preentrenados, para no descargar nada) → calibración → evaluación → run real en MLflow → (opcional) registro en
el Model Registry. Todo queda etiquetado `smoke_test=true`: la aplicación lo trata como DEMO / no validado.

Uso:  python -m potato_blight.smoke --arch resnet50 --register
      python -m potato_blight.smoke --arch cnn_vit --cv --epochs 2
"""

import argparse
import json
import logging
import tempfile
from pathlib import Path

from potato_blight.config import ExperimentCfg
from potato_blight.data.registry import load_registry
from potato_blight.data.synthetic import generate
from potato_blight.mlflow_utils import setup
from potato_blight.prepare import prepare
from potato_blight.train import run_cv, run_final

log = logging.getLogger("potato_blight")
DATASET_ID = "sintetico_smoke"


def smoke_config(arch: str, root: Path, *, epochs: int, img_size: int, experiment: str) -> ExperimentCfg:
    return ExperimentCfg.model_validate({
        "experiment": experiment,
        "architecture": arch,
        "pretrained": False,
        "img_size": img_size,
        "smoke_test": True,
        "train": {"epochs": epochs, "batch_size": 8, "lr": 1e-3, "patience": epochs, "amp": False,
                  "num_workers": 0, "seed": 2026},
        "data": {"manifest": str(root / "manifest.csv"), "roots": {DATASET_ID: str(root / "imagenes")},
                 "train_datasets": [DATASET_ID], "external_datasets": [], "n_splits": 3},
    })


def run(arch: str, *, epochs: int = 1, img_size: int = 96, cv: bool = False, register: bool = False,
        experiment: str = "papasana-smoke", workdir: str | None = None) -> dict:
    tmp = tempfile.TemporaryDirectory() if workdir is None else None
    root = Path(workdir or tmp.name)
    try:
        generate(root / "imagenes", plants_per_class=6, views_per_plant=2, size=128)
        cfg = smoke_config(arch, root, epochs=epochs, img_size=img_size, experiment=experiment)
        df, report = prepare(cfg, load_registry())
        df.to_csv(cfg.data.manifest, index=False)
        uri = setup(cfg.experiment)
        out = {"tracking_uri": uri, "experiment": cfg.experiment, "architecture": arch, "datos": report}
        if cv:
            out["cv"] = run_cv(cfg, df)
        final = run_final(cfg, df, val_fold=0, cv_parent_run_id=out.get("cv", {}).get("parent_run_id"))
        out["final_run_id"] = final.run_id
        out["metricas_validacion"] = {k: v for k, v in final.metrics.items() if k.startswith("val_macro")}
        if register:
            from potato_blight.register import register_run

            name, version = register_run(final.run_id, "Prueba de humo con imágenes sintéticas (sin valor científico)")
            out["modelo_registrado"] = {"name": name, "version": version}
        return out
    finally:
        if tmp is not None:
            tmp.cleanup()


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arch", default="resnet50")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--img-size", type=int, default=96)
    ap.add_argument("--cv", action="store_true", help="Además, validación cruzada de 3 particiones")
    ap.add_argument("--register", action="store_true", help="Registrar el modelo final en el Model Registry")
    ap.add_argument("--experiment", default="papasana-smoke")
    args = ap.parse_args(argv)
    out = run(args.arch, epochs=args.epochs, img_size=args.img_size, cv=args.cv, register=args.register,
              experiment=args.experiment)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
