import hashlib
import json
from types import SimpleNamespace

import pytest

from potato_blight.publication import publish


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("dataset_id,label,fold,source_group,width,height\n"
                        "plantvillage_papa,sano,0,hoja-a,256,256\n"
                        "plantvillage_papa,sano,1,hoja-b,256,256\n"
                        "plantdoc_papa,sano,-1,externa,400,300\n", encoding="utf-8")
    manifest.with_suffix(".informe.json").write_text(json.dumps({
        "imagenes_originales": 3, "duplicados_exactos_eliminados": 0,
        "imagenes_con_etiquetas_en_conflicto": 0}), encoding="utf-8")
    source = tmp_path / "source"
    model = source / "resnet50/model"
    model.mkdir(parents=True)
    (model / "model.pt").write_bytes(b"checkpoint-unitario")
    digest = hashlib.sha256((model / "model.pt").read_bytes()).hexdigest()
    config = {"architecture": "resnet50", "experiment": "unit-experiment", "img_size": 224,
              "train": {"seed": 2026}, "data": {"train_datasets": ["plantvillage_papa"],
                                                "external_datasets": ["plantdoc_papa"]}}
    result = {"contract": {"manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                           "configs": [config], "validation_fold": 1},
              "models": [{"architecture": "resnet50", "run_id": "unit-run", "metrics": {"val_macro_f1": 0.8},
                          "best_epoch": 1, "evaluation": {"val": {"classes": ["sano"]}},
                          "verification": {"checkpoint_sha256": digest},
                          "probe": {"parameters_three_classes": 3}, "checkpoint_mb": 0.1}],
              "gpu": "GPU unitaria", "torch": "unit", "fingerprint": "unit", "selection": {}, "limits": []}
    (source / "results.json").write_text(json.dumps(result), encoding="utf-8")
    (source / "model_sources.json").write_text("[]", encoding="utf-8")
    run = SimpleNamespace(info=SimpleNamespace(status="FINISHED", start_time=1790000000000),
                          data=SimpleNamespace(tags={}))
    fake = SimpleNamespace(get_run=lambda _: run,
                           get_metric_history=lambda *_: [SimpleNamespace(step=1, value=0.8)])
    monkeypatch.setattr("potato_blight.publication.mlflow.MlflowClient", lambda: fake)
    return source, manifest, tmp_path / "published", model


def test_publicar_preserva_metricas_y_no_copia_pesos_ni_rutas(inputs):
    source, manifest, output, _ = inputs
    target = publish(source, output, manifest)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["models"][0]["metrics"]["val_macro_f1"] == 0.8
    assert data["models"][0]["history"]["val_loss"][0] == {"step": 1, "value": 0.8}
    assert data["data"]["train"] == 1 and data["data"]["validation"] == 1
    assert data["data"]["resolution"][0]["width"] == 3
    assert [p.suffix for p in output.iterdir()] == [".json"]
    assert str(source) not in target.read_text(encoding="utf-8")


def test_publicar_rechaza_manifest_distinto(inputs):
    source, manifest, output, _ = inputs
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        publish(source, output, manifest)
    assert not output.exists()


def test_publicar_rechaza_checkpoint_modificado(inputs):
    source, manifest, output, model = inputs
    (model / "model.pt").write_bytes(b"otros-pesos")
    with pytest.raises(ValueError, match="Checkpoint"):
        publish(source, output, manifest)
    assert not output.exists()
