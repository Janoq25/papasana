import mlflow
import pandas as pd
import pytest

from potato_blight import CLASSES
from potato_blight.config import load_config
from potato_blight.data.splits import LeakageError, check_no_leakage
from potato_blight.nested import run_nested
from potato_blight.train import FoldResult


def test_configuracion_hereda_tres_niveles_y_rechaza_ciclos(tmp_path):
    base = load_config("configs/resnet50_laptop.yaml")
    assert base.train.batch_size == 8 and base.train.require_cuda
    assert base.data.n_splits == 5 and base.tuning.inner_splits == 3
    path = tmp_path / "loop.yaml"
    path.write_text("base: loop.yaml", encoding="utf-8")
    with pytest.raises(ValueError, match="circular"):
        load_config(path)


def test_ids_de_fuente_impiden_fuga_aunque_el_hash_cambie():
    left = pd.DataFrame({"group_id": ["hoja1"], "sha256": ["foto1"]})
    right = pd.DataFrame({"group_id": ["hoja1"], "sha256": ["foto2"]})
    with pytest.raises(LeakageError):
        check_no_leakage({"train": left, "test": right})


def test_busqueda_anidada_nunca_entrena_con_outer_test_ni_plantdoc(tmp_path, monkeypatch):
    mlflow.set_tracking_uri(f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}")
    mlflow.set_experiment("nested-isolation")
    cfg = load_config("configs/resnet50_laptop.yaml", overrides={"tuning": {"n_trials": 2}})
    rows = [{"dataset_id": "plantvillage_papa", "path": f"{label}-{group}.jpg", "label": label,
             "sha256": f"hash-{label}-{group}", "group_id": f"leaf-{label}-{group}", "fold": group % 5}
            for label in CLASSES for group in range(15)]
    rows.append({"dataset_id": "plantdoc_papa", "path": "externa.jpg", "label": CLASSES[0],
                 "sha256": "externa", "group_id": "externa", "fold": -1})
    df = pd.DataFrame(rows)
    held_out = set(df[df["fold"] == 0]["path"])
    calls = []

    def fake_train(candidate, parts, **kwargs):
        calls.append((parts, kwargs))
        check_no_leakage(parts)
        for name in ("train", "val"):
            assert not set(parts[name]["path"]) & held_out
            assert set(parts[name]["dataset_id"]) == {"plantvillage_papa"}
        with mlflow.start_run(run_name=kwargs["run_name"], nested=True) as run:
            return FoldResult(run.info.run_id, {"val_macro_f1": 0.7, "test_macro_f1": 0.6}, 1, False)

    monkeypatch.setattr("potato_blight.nested.train_split", fake_train)
    result = run_nested(cfg, df, folds=[0], output=tmp_path / "configs")
    assert len(calls) == 2 * 3 + 1
    assert all(set(parts) == {"train", "val"} for parts, _ in calls[:-1])
    assert set(calls[-1][0]["test"]["path"]) == held_out
    assert result["summary"]["cv_mean_test_macro_f1"] == pytest.approx(0.6)
