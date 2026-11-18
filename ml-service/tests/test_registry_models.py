"""Carga de modelos entrenados (formato de potato_blight) y recarga en caliente."""

import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from potato_blight.models import build_model, make_config, save_model_dir

import app.main as main
from app.model import CLASSES, LoadResult, demo_predictor, load_predictor, predictor_from_dir


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), (40, 130, 40)).save(buf, "PNG")
    return buf.getvalue()


@pytest.mark.parametrize("arch", ["resnet50", "effnet_att_bilstm"])
def test_modelo_entrenado_se_carga_y_predice_con_gradcam(tmp_path, arch):
    model = build_model(arch, 3, img_size=64)
    save_model_dir(model, make_config(arch, CLASSES, img_size=64, temperature=1.3), tmp_path / "m")
    p = predictor_from_dir(tmp_path / "m", name=f"papasana-{arch}", version="4", run_id="abc")
    assert p.info.key == f"papasana-{arch}:v4" and not p.info.is_demo and p.info.temperature == 1.3
    out = p.predict(_png())
    assert set(out["probabilities"]) == set(CLASSES) and out["gradcam_png_b64"]
    assert out["model"]["source"] == "mlflow" and out["model"]["mlflow"]["run_id"] == "abc"


def test_modelo_de_prueba_de_humo_se_marca_como_demo(tmp_path):
    save_model_dir(build_model("resnet50", 3, img_size=64),
                   make_config("resnet50", CLASSES, img_size=64, smoke_test=True), tmp_path / "m")
    p = predictor_from_dir(tmp_path / "m", name="papasana-resnet50", version="1", run_id="r")
    assert p.info.is_demo and p.info.display_name.startswith("SMOKE TEST / no validado")


def test_clases_incompatibles_se_rechazan(tmp_path):
    save_model_dir(build_model("resnet50", 2, img_size=64),
                   make_config("resnet50", ["sano", "enfermo"], img_size=64), tmp_path / "m")
    with pytest.raises(ValueError):
        predictor_from_dir(tmp_path / "m", name="papasana-resnet50", version="2", run_id="r")


def test_sin_mlflow_o_caido_se_sirve_el_demo():
    assert load_predictor("").status == "demo_sin_mlflow"
    r = load_predictor("http://127.0.0.1:9")  # nada escucha en ese puerto
    assert r.status == "error_produccion" and r.predictor.info.is_demo
    with pytest.raises(httpx.HTTPError):
        load_predictor("http://127.0.0.1:9", fallback_to_demo=False)


def test_recarga_cambia_el_modelo_o_conserva_el_actual(monkeypatch, tmp_path):
    save_model_dir(build_model("resnet50", 3, img_size=64), make_config("resnet50", CLASSES, img_size=64),
                   tmp_path / "m")
    nuevo = predictor_from_dir(tmp_path / "m", name="papasana-resnet50", version="7", run_id="r7")
    with TestClient(main.app) as c:
        assert c.get("/model").json()["key"] == "demo-resnet50-imagenet-v1"
        monkeypatch.setattr(main, "load_predictor", lambda **_: LoadResult(nuevo, "produccion"))
        r = c.post("/reload")
        assert r.status_code == 200 and r.json()["key"] == "papasana-resnet50:v7"
        assert c.get("/model").json()["load_status"]["estado"] == "produccion"

        def falla(**_):
            raise RuntimeError("descarga interrumpida")

        monkeypatch.setattr(main, "load_predictor", falla)
        assert c.post("/reload").status_code == 503
        assert c.get("/model").json()["key"] == "papasana-resnet50:v7"  # se conserva el modelo anterior
    assert demo_predictor().info.is_demo
