"""Pipeline completo con MLflow local (archivo SQLite temporal) e imágenes sintéticas."""

import json

import mlflow
import pandas as pd
import pytest

from potato_blight import CLASSES
from potato_blight.compare import compare
from potato_blight.smoke import run


@pytest.fixture
def local_mlflow(tmp_path, monkeypatch):
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    yield uri
    mlflow.end_run()


def test_prueba_de_humo_registra_run_modelo_y_comparacion(local_mlflow, tmp_path):
    out = run("resnet50", epochs=1, img_size=64, cv=True, register=True, experiment="smoke-test",
              workdir=str(tmp_path / "w"))
    client = mlflow.MlflowClient()
    final = client.get_run(out["final_run_id"])
    assert final.data.tags["smoke_test"] == "true" and final.data.tags["run_type"] == "final"
    assert "temperature" in final.data.metrics and "val_macro_f1" in final.data.metrics
    assert final.data.tags["cv_parent_run_id"] == out["cv"]["parent_run_id"]
    files = {a.path for a in client.list_artifacts(out["final_run_id"])}
    assert {"model", "evaluation.json"} <= files
    model_files = {a.path for a in client.list_artifacts(out["final_run_id"], "model")}
    assert model_files == {"model/model.pt", "model/model_config.json"}
    reg = out["modelo_registrado"]
    mv = client.get_model_version(reg["name"], reg["version"])
    assert reg["name"] == "papasana-resnet50" and mv.tags["smoke_test"] == "true"
    assert json.loads(mv.tags["metrics_summary"])  # resumen de métricas para el laboratorio
    assert not client.get_registered_model(reg["name"]).aliases  # registrar NO promueve a producción

    # Validación cruzada: un run por partición con predicciones fuera de partición
    folds = client.search_runs([final.info.experiment_id], "tags.run_type = 'cv_fold'")
    assert len(folds) == 3
    preds = pd.read_csv(client.download_artifacts(folds[0].info.run_id, "predictions.csv", str(tmp_path)))
    assert {f"p_{c}" for c in CLASSES} <= set(preds.columns)

    cmp_ = compare("smoke-test", include_smoke=True)
    assert cmp_["estado"] == "ok" and cmp_["modelos"] == ["resnet50"] and cmp_["oof_imagenes"] > 0
    assert compare("smoke-test")["estado"] == "sin_experimentos"  # sin smoke: no hay experimentos reales
